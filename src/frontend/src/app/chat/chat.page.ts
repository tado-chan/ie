// src/frontend/src/app/chat/chat.page.ts
import { Component, OnInit, OnDestroy, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IonicModule, IonContent } from '@ionic/angular';
import { Subscription } from 'rxjs';
import { ChatService, AnalysisResponse } from '../services/chat.service';

interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
  status?: 'sending' | 'sent' | 'error';
}

@Component({
  selector: 'app-chat',
  templateUrl: './chat.page.html',
  styleUrls: ['./chat.page.scss'],
  standalone: true,
  imports: [IonicModule, CommonModule, FormsModule]
})
export class ChatPage implements OnInit, OnDestroy {
  @ViewChild(IonContent) content!: IonContent;

  messages: Message[] = [];
  newMessage = '';
  isLoading = false;
  conversationId: string | null = null;
  private analysisSubscription?: Subscription;

  constructor(private chatService: ChatService) { }

  ngOnInit() {
    // 初期メッセージ
    this.messages.push({
      id: '1',
      content: 'こんにちは！報連相でお困りのことはありませんか？どんなことでもお気軽にご相談ください。',
      role: 'assistant',
      timestamp: new Date(),
    });

    // 分析結果の購読
    this.subscribeToAnalysisResults();
  }

  ngOnDestroy() {
    if (this.analysisSubscription) {
      this.analysisSubscription.unsubscribe();
    }
  }

  private subscribeToAnalysisResults() {
    this.analysisSubscription = this.chatService.analysis$.subscribe((response: AnalysisResponse | null) => {
      if (response) {
        if (response.status === 'completed' && response.analysis) {
          // 分析結果を受信した場合、アシスタントメッセージとして表示
          this.messages.push({
            id: Date.now().toString(),
            content: response.analysis,
            role: 'assistant',
            timestamp: new Date(),
          });
          this.isLoading = false;
          this.scrollToBottom();

        } else if (response.status === 'error') {
          // エラーメッセージを受信した場合
          this.messages.push({
            id: Date.now().toString(),
            content: response.error || '申し訳ございません。処理中にエラーが発生しました。もう一度お試しください。',
            role: 'assistant',
            timestamp: new Date(),
          });
          this.isLoading = false;
          this.scrollToBottom();
        }
        // status === 'processing' の場合は待機状態を継続
      }
    });
  }

  async sendMessage() {
    if (!this.newMessage.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: this.newMessage,
      role: 'user',
      timestamp: new Date(),
      status: 'sending',
    };

    this.messages.push(userMessage);
    const messageContent = this.newMessage;
    this.newMessage = '';
    this.isLoading = true;
    this.scrollToBottom();

    try {
      // APIを呼び出し
      const response = await this.chatService.sendMessage(
        messageContent,
        this.conversationId
      );

      // ステータスを更新
      userMessage.status = 'sent';
      this.conversationId = response.conversationId;

      // 即座に確認メッセージを表示（分析結果を待つ間）
      this.messages.push({
        id: Date.now().toString(),
        content: `承知いたしました。「${messageContent}」についてのご相談ですね。状況を整理させていただきます。`,
        role: 'assistant',
        timestamp: new Date(),
      });
      this.scrollToBottom();

      // 分析結果はsubscribeToAnalysisResults()で受信される

    } catch (error) {
      console.error('Error sending message:', error);
      userMessage.status = 'error';
      this.isLoading = false;

      // エラー時のメッセージ
      this.messages.push({
        id: Date.now().toString(),
        content: '申し訳ございません。現在システムの調整中です。しばらくお待ちください。',
        role: 'assistant',
        timestamp: new Date(),
      });
      this.scrollToBottom();
    }
  }

  private scrollToBottom() {
    setTimeout(() => {
      if (this.content) {
        this.content.scrollToBottom(300);
      }
    }, 100);
  }

  handleKeyPress(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }
}