// src/frontend/src/app/services/chat.service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { BehaviorSubject, Observable, interval, firstValueFrom } from 'rxjs';
import { switchMap, takeWhile } from 'rxjs/operators';
import { environment } from '../../environments/environment';

export interface ChatResponse {
    conversationId: string;
    status: 'processing' | 'completed' | 'error';
    message: string;
    executionArn?: string;
}

export interface AnalysisResponse {
    conversationId: string;
    status: 'processing' | 'completed' | 'error';
    analysis?: string;
    category?: string;
    recommendedRecipient?: string;
    timestamp?: string;
    error?: string;
}

@Injectable({
    providedIn: 'root'
})
export class ChatService {
    private apiUrl = environment.apiUrl + '/api/v1/chat';
    private analysisSubject = new BehaviorSubject<AnalysisResponse | null>(null);
    public analysis$ = this.analysisSubject.asObservable();

    constructor(private http: HttpClient) { }

    async sendMessage(message: string, conversationId: string | null): Promise<ChatResponse> {
        // 開発中はモックレスポンスを返す
        if (environment.production === false && !environment.apiUrl.includes('amazonaws.com')) {
            console.log('Using mock response for development');
            return new Promise((resolve) => {
                const mockConversationId = conversationId || 'mock-' + Date.now();

                // モック分析結果を遅延して配信
                setTimeout(() => {
                    this.analysisSubject.next({
                        conversationId: mockConversationId,
                        status: 'completed',
                        analysis: 'この相談内容について分析しました。上司への報告が必要な案件のようです。まず直属の上司に状況を整理して報告することをお勧めします。具体的には以下の手順で進めてください：\n\n1. 問題の概要を整理\n2. 現在の状況と影響範囲を明確化\n3. 可能な解決策の検討\n4. 上司への報告タイミングの調整',
                        category: '業務報告',
                        recommendedRecipient: '直属の上司'
                    });
                }, 3000);

                resolve({
                    conversationId: mockConversationId,
                    status: 'processing',
                    message: 'Mock response'
                });
            });
        }

        const headers = new HttpHeaders({
            'Content-Type': 'application/json',
        });

        const body = {
            message: message,
            conversationId: conversationId,
            context: {
                timestamp: new Date().toISOString()
            }
        };

        try {
            const response = await firstValueFrom(
                this.http.post<ChatResponse>(this.apiUrl, body, { headers })
            );

            // 分析結果のポーリングを開始
            if (response.status === 'processing') {
                this.startPolling(response.conversationId);
            }

            return response;
        } catch (error) {
            console.error('Error sending message:', error);
            throw error;
        }
    }

    private startPolling(conversationId: string) {
        // 30秒間、2秒間隔でポーリング
        const polling$ = interval(2000).pipe(
            switchMap(() => this.getAnalysisStatus(conversationId)),
            takeWhile((response) => response.status === 'processing', true)
        );

        polling$.subscribe({
            next: (response) => {
                this.analysisSubject.next(response);
                if (response.status === 'completed' || response.status === 'error') {
                    console.log('Polling completed:', response);
                }
            },
            error: (error) => {
                console.error('Polling error:', error);
                this.analysisSubject.next({
                    conversationId: conversationId,
                    status: 'error',
                    error: 'ポーリング中にエラーが発生しました'
                });
            }
        });
    }

    private async getAnalysisStatus(conversationId: string): Promise<AnalysisResponse> {
        try {
            const response = await firstValueFrom(
                this.http.get<AnalysisResponse>(`${this.apiUrl}/${conversationId}/status`)
            );
            return response;
        } catch (error) {
            console.error('Error getting analysis status:', error);
            return {
                conversationId: conversationId,
                status: 'error',
                error: 'ステータス取得エラー'
            };
        }
    }

    async getConversationHistory(conversationId: string) {
        return firstValueFrom(
            this.http.get(`${this.apiUrl}/${conversationId}`)
        );
    }
}