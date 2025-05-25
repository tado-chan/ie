import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, Subject } from 'rxjs';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';

export interface WebSocketMessage {
    action: string;
    data: any;
    conversationId?: string;
    timestamp?: string;
}

export interface ChatMessage {
    id: string;
    content: string;
    role: 'user' | 'assistant';
    timestamp: Date;
    status?: 'sending' | 'sent' | 'error';
    suggestion?: SuggestionData;
}

export interface SuggestionData {
    recommendedPerson: string;
    department: string;
    role: string;
    reason: string;
    suggestedMessage: string;
    urgency: 'high' | 'medium' | 'low';
}

@Injectable({
    providedIn: 'root'
})
export class WebSocketService {
    private socket: WebSocket | null = null;
    private connectionStatus$ = new BehaviorSubject<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
    private messages$ = new Subject<WebSocketMessage>();
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 1000;

    constructor(private authService: AuthService) {
        // 認証状態の変化を監視
        this.authService.isAuthenticated$.subscribe(isAuthenticated => {
            if (isAuthenticated) {
                this.connect();
            } else {
                this.disconnect();
            }
        });
    }

    /**
     * WebSocket接続を確立
     */
    async connect(): Promise<void> {
        if (this.socket?.readyState === WebSocket.OPEN) {
            return;
        }

        try {
            this.connectionStatus$.next('connecting');

            // 認証トークンを取得
            const token = await this.authService.getIdToken();

            // WebSocket URLにトークンをクエリパラメータとして追加
            const wsUrl = `${environment.websocketUrl}?token=${token}`;

            this.socket = new WebSocket(wsUrl);

            this.setupEventHandlers();
        } catch (error) {
            console.error('WebSocket connection error:', error);
            this.connectionStatus$.next('error');
            this.scheduleReconnect();
        }
    }

    /**
     * WebSocketイベントハンドラーの設定
     */
    private setupEventHandlers(): void {
        if (!this.socket) return;

        this.socket.onopen = () => {
            console.log('WebSocket connected');
            this.connectionStatus$.next('connected');
            this.reconnectAttempts = 0;
        };

        this.socket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data) as WebSocketMessage;
                this.messages$.next(message);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.connectionStatus$.next('error');
        };

        this.socket.onclose = () => {
            console.log('WebSocket disconnected');
            this.connectionStatus$.next('disconnected');
            this.scheduleReconnect();
        };
    }

    /**
     * 再接続のスケジューリング
     */
    private scheduleReconnect(): void {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * メッセージを送信
     */
    sendMessage(message: WebSocketMessage): void {
        if (this.socket?.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(message));
        } else {
            console.error('WebSocket is not connected');
            throw new Error('WebSocket is not connected');
        }
    }

    /**
     * チャットメッセージを送信
     */
    sendChatMessage(conversationId: string, content: string): void {
        const message: WebSocketMessage = {
            action: 'sendmessage',
            data: {
                conversationId,
                message: content,
                timestamp: new Date().toISOString()
            }
        };

        this.sendMessage(message);
    }

    /**
     * ステータスを取得
     */
    getStatus(conversationId: string): void {
        const message: WebSocketMessage = {
            action: 'status',
            data: {
                conversationId
            }
        };

        this.sendMessage(message);
    }

    /**
     * WebSocket接続を切断
     */
    disconnect(): void {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.connectionStatus$.next('disconnected');
    }

    /**
     * 接続状態のObservable
     */
    getConnectionStatus(): Observable<'disconnected' | 'connecting' | 'connected' | 'error'> {
        return this.connectionStatus$.asObservable();
    }

    /**
     * メッセージのObservable
     */
    getMessages(): Observable<WebSocketMessage> {
        return this.messages$.asObservable();
    }

    /**
     * 特定の会話IDのメッセージをフィルタリング
     */
    getConversationMessages(conversationId: string): Observable<WebSocketMessage> {
        return new Observable(subscriber => {
            this.messages$.subscribe(message => {
                if (message.conversationId === conversationId || !message.conversationId) {
                    subscriber.next(message);
                }
            });
        });
    }

    /**
     * 接続状態を確認
     */
    isConnected(): boolean {
        return this.socket?.readyState === WebSocket.OPEN;
    }

    /**
     * 手動で再接続
     */
    reconnect(): void {
        this.reconnectAttempts = 0;
        this.connect();
    }
}