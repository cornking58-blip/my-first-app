import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import axios, { isAxiosError } from 'axios';
import { AmbientBackground } from '../src/components/AmbientBackground';
import { BrandLogo } from '../src/components/BrandLogo';
import { AIAuthGate } from '../src/components/AIAuthGate';
import { useAuth } from '../src/auth/AuthContext';
import { colors, shadows } from '../src/theme/colors';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type ChatRole = 'user' | 'assistant';

interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  created_at: string;
}

interface AIChat {
  id: string;
  title: string;
  context_type: 'general' | 'comparison';
  context?: Record<string, unknown>;
  messages?: ChatMessage[];
  last_message_preview?: string;
  created_at: string;
  updated_at: string;
}

const getParam = (value?: string | string[]) => (
  Array.isArray(value) ? value[0] : value
);

const getOptionalNumber = (value?: string) => {
  if (!value) return undefined;
  const parsed = Number(value.replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : undefined;
};

const formatMessageText = (value: string) => value
  .replace(/\*\*([\s\S]*?)\*\*/g, '$1')
  .replace(/__([\s\S]*?)__/g, '$1')
  .replace(/^\s*#{1,6}\s*/gm, '')
  .replace(/`/g, '')
  .replace(/^\s*[-*]\s+/gm, '• ')
  .replace(/\n{3,}/g, '\n\n')
  .trim();

export default function AIChatScreen() {
  const router = useRouter();
  const {
    loading: authLoading,
    token,
    user,
    logout,
  } = useAuth();
  const routeParams = useLocalSearchParams<{
    context_type?: string | string[];
    left_key?: string | string[];
    right_key?: string | string[];
    left_name?: string | string[];
    right_name?: string | string[];
    left_price?: string | string[];
    right_price?: string | string[];
    left_rate?: string | string[];
    right_rate?: string | string[];
    crop?: string | string[];
  }>();
  const scrollRef = useRef<ScrollView>(null);
  const [chats, setChats] = useState<AIChat[]>([]);
  const [activeChat, setActiveChat] = useState<AIChat | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const contextType = getParam(routeParams.context_type) === 'comparison'
    ? 'comparison'
    : 'general';
  const leftName = getParam(routeParams.left_name) || 'Препарат А';
  const rightName = getParam(routeParams.right_name) || 'Препарат Б';

  const comparisonContext = useMemo(() => {
    if (contextType !== 'comparison') return {};
    return {
      left_key: getParam(routeParams.left_key),
      right_key: getParam(routeParams.right_key),
      left_price: getOptionalNumber(getParam(routeParams.left_price)),
      right_price: getOptionalNumber(getParam(routeParams.right_price)),
      left_rate: getOptionalNumber(getParam(routeParams.left_rate)),
      right_rate: getOptionalNumber(getParam(routeParams.right_rate)),
      crop: getParam(routeParams.crop),
    };
  }, [
    contextType,
    routeParams.left_key,
    routeParams.right_key,
    routeParams.left_price,
    routeParams.right_price,
    routeParams.left_rate,
    routeParams.right_rate,
    routeParams.crop,
  ]);

  const requestHeaders = () => ({
    headers: { Authorization: `Bearer ${token}` },
  });

  const loadChats = async () => {
    if (!token) return;
    try {
      const response = await axios.get(`${API_URL}/api/ai/chats`, requestHeaders());
      setChats(response.data);
      setError(null);
    } catch {
      setError('Не удалось загрузить историю чатов');
    }
  };

  useEffect(() => {
    const initialize = async () => {
      if (authLoading) return;
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const response = await axios.get(
          `${API_URL}/api/ai/chats`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        setChats(response.data);
        setError(null);
      } catch {
        setError('Не удалось загрузить историю чатов');
      }
      setLoading(false);
    };
    initialize();
  }, [authLoading, token]);

  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80);
    }
  }, [messages, sending]);

  const openChat = async (chat: AIChat) => {
    setLoading(true);
    try {
      const response = await axios.get(
        `${API_URL}/api/ai/chats/${chat.id}`,
        requestHeaders(),
      );
      setActiveChat(response.data);
      setMessages(response.data.messages || []);
      setShowHistory(false);
      setError(null);
    } catch {
      setError('Не удалось открыть чат');
    } finally {
      setLoading(false);
    }
  };

  const startNewChat = () => {
    setActiveChat(null);
    setMessages([]);
    setInput('');
    setError(null);
    setShowHistory(false);
  };

  const createChat = async () => {
    const title = contextType === 'comparison'
      ? `${leftName} и ${rightName}`
      : 'Новый вопрос';
    const response = await axios.post(
      `${API_URL}/api/ai/chats`,
      {
        context_type: contextType,
        title,
        context: comparisonContext,
      },
      requestHeaders(),
    );
    const chat = response.data as AIChat;
    setActiveChat(chat);
    return chat;
  };

  const getErrorText = (requestError: unknown) => {
    if (isAxiosError(requestError)) {
      const detail = requestError.response?.data?.detail;
      if (typeof detail === 'string') return detail;
    }
    return 'Не удалось получить ответ. Попробуйте ещё раз.';
  };

  const sendMessage = async () => {
    const content = input.trim();
    if (!content || sending || !token) return;

    setSending(true);
    setError(null);
    setInput('');
    const temporaryMessage: ChatMessage = {
      id: `temporary-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages(current => [...current, temporaryMessage]);

    try {
      const chat = activeChat || await createChat();
      const response = await axios.post(
        `${API_URL}/api/ai/chats/${chat.id}/messages`,
        { content },
        requestHeaders(),
      );
      setMessages(current => [
        ...current.filter(message => message.id !== temporaryMessage.id),
        response.data.user_message,
        response.data.assistant_message,
      ]);
      setActiveChat(current => ({
        ...(current || chat),
        title: response.data.chat_title || current?.title || chat.title,
      }));
      await loadChats();
    } catch (requestError) {
      setMessages(current => current.filter(message => message.id !== temporaryMessage.id));
      setInput(content);
      setError(getErrorText(requestError));
    } finally {
      setSending(false);
    }
  };

  const deleteChat = async (chatId: string) => {
    try {
      await axios.delete(`${API_URL}/api/ai/chats/${chatId}`, requestHeaders());
      if (activeChat?.id === chatId) startNewChat();
      setChats(current => current.filter(chat => chat.id !== chatId));
    } catch {
      setError('Не удалось удалить чат');
    }
  };

  const promptSuggestions = contextType === 'comparison'
    ? [
        'Объясни итог сравнения простыми словами',
        'В чём практическая разница составов?',
        'Как меняется вывод с учётом цены на гектар?',
      ]
    : [
        'Какие препараты содержат флорасулам?',
        'Объясни HRAC простыми словами',
        'Как сравнивать гербициды по действующим веществам?',
      ];

  if (authLoading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <AmbientBackground />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primaryBright} />
          <Text style={styles.loadingText}>Проверяем аккаунт...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!user || !token) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <AIAuthGate onBack={() => router.back()} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <AmbientBackground />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <View style={styles.header}>
          <TouchableOpacity style={styles.headerButton} onPress={() => router.back()}>
            <Ionicons name="arrow-back" size={22} color={colors.text} />
          </TouchableOpacity>
          <View style={styles.headerCenter}>
            <BrandLogo compact />
            <Text style={styles.headerSubtitle}>AI-ассистент</Text>
          </View>
          <TouchableOpacity
            style={[styles.headerButton, showHistory && styles.headerButtonActive]}
            onPress={() => setShowHistory(current => !current)}
          >
            <Ionicons name="time-outline" size={22} color={colors.text} />
          </TouchableOpacity>
        </View>

        {loading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={colors.primaryBright} />
            <Text style={styles.loadingText}>Загружаем чат...</Text>
          </View>
        ) : showHistory ? (
          <ScrollView contentContainerStyle={styles.historyContent}>
            <View style={styles.historyTitleRow}>
              <View>
                <Text style={styles.historyTitle}>История чатов</Text>
                <Text style={styles.historySubtitle}>
                  {user.access.plan === 'trial'
                    ? 'Пробный доступ · чаты сохраняются в аккаунте'
                    : 'Чаты сохраняются в вашем аккаунте'}
                </Text>
              </View>
              <View style={styles.historyActions}>
                <TouchableOpacity style={styles.logoutButton} onPress={logout}>
                  <Ionicons name="log-out-outline" size={17} color={colors.textSecondary} />
                </TouchableOpacity>
                <TouchableOpacity style={styles.newChatButton} onPress={startNewChat}>
                  <Ionicons name="add" size={18} color={colors.white} />
                  <Text style={styles.newChatButtonText}>Новый</Text>
                </TouchableOpacity>
              </View>
            </View>

            {chats.length === 0 ? (
              <View style={styles.emptyHistory}>
                <Ionicons name="chatbubbles-outline" size={40} color={colors.textMuted} />
                <Text style={styles.emptyHistoryText}>Здесь появятся сохранённые диалоги</Text>
              </View>
            ) : (
              chats.map(chat => (
                <View key={chat.id} style={styles.historyCard}>
                  <TouchableOpacity style={styles.historyCardContent} onPress={() => openChat(chat)}>
                    <Text style={styles.historyCardTitle} numberOfLines={1}>{chat.title}</Text>
                    <Text style={styles.historyCardPreview} numberOfLines={2}>
                      {chat.last_message_preview || 'Диалог пока пуст'}
                    </Text>
                    <Text style={styles.historyCardType}>
                      {chat.context_type === 'comparison' ? 'Сравнение препаратов' : 'Общий вопрос'}
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.deleteButton} onPress={() => deleteChat(chat.id)}>
                    <Ionicons name="trash-outline" size={18} color={colors.danger} />
                  </TouchableOpacity>
                </View>
              ))
            )}
          </ScrollView>
        ) : (
          <>
            {contextType === 'comparison' && !activeChat ? (
              <View style={styles.contextBanner}>
                <Ionicons name="git-compare-outline" size={19} color={colors.primaryBright} />
                <View style={styles.contextBannerCopy}>
                  <Text style={styles.contextBannerLabel}>ИИ видит текущее сравнение</Text>
                  <Text style={styles.contextBannerText} numberOfLines={1}>{leftName} · {rightName}</Text>
                </View>
              </View>
            ) : null}

            <ScrollView
              ref={scrollRef}
              style={styles.messages}
              contentContainerStyle={styles.messagesContent}
              keyboardShouldPersistTaps="handled"
            >
              {messages.length === 0 ? (
                <View style={styles.welcome}>
                  <View style={styles.aiOrb}>
                    <Ionicons name="sparkles" size={28} color={colors.white} />
                  </View>
                  <Text style={styles.welcomeTitle}>
                    {contextType === 'comparison' ? 'Разберём сравнение' : 'Спросите bAIkov AI'}
                  </Text>
                  <Text style={styles.welcomeText}>
                    {contextType === 'comparison'
                      ? 'ИИ использует составы, нормы, HRAC, цены и итог текущего сравнения.'
                      : 'Ответы опираются на данные единого справочника пестицидов РФ.'}
                  </Text>
                  <View style={styles.suggestions}>
                    {promptSuggestions.map(suggestion => (
                      <TouchableOpacity
                        key={suggestion}
                        style={styles.suggestion}
                        onPress={() => setInput(suggestion)}
                      >
                        <Text style={styles.suggestionText}>{suggestion}</Text>
                        <Ionicons name="arrow-forward" size={15} color={colors.primaryBright} />
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              ) : (
                messages.map(message => (
                  <View
                    key={message.id}
                    style={[
                      styles.messageBubble,
                      message.role === 'user' ? styles.userMessage : styles.assistantMessage,
                    ]}
                  >
                    {message.role === 'assistant' ? (
                      <View style={styles.assistantLabel}>
                        <Ionicons name="sparkles" size={13} color={colors.primaryBright} />
                        <Text style={styles.assistantLabelText}>bAIkov AI</Text>
                      </View>
                    ) : null}
                    <Text style={styles.messageText}>{formatMessageText(message.content)}</Text>
                  </View>
                ))
              )}

              {sending ? (
                <View style={[styles.messageBubble, styles.assistantMessage, styles.typingBubble]}>
                  <ActivityIndicator size="small" color={colors.primaryBright} />
                  <Text style={styles.typingText}>Анализирую данные...</Text>
                </View>
              ) : null}
            </ScrollView>

            {error ? (
              <View style={styles.errorBar}>
                <Ionicons name="alert-circle-outline" size={17} color={colors.danger} />
                <Text style={styles.errorText}>{error}</Text>
              </View>
            ) : null}

            <View style={styles.composerArea}>
              <View style={styles.composer}>
                <TextInput
                  style={styles.input}
                  placeholder="Напишите вопрос..."
                  placeholderTextColor={colors.textMuted}
                  value={input}
                  onChangeText={setInput}
                  multiline
                  maxLength={4000}
                />
                <TouchableOpacity
                  style={[styles.sendButton, (!input.trim() || sending) && styles.sendButtonDisabled]}
                  onPress={sendMessage}
                  disabled={!input.trim() || sending}
                >
                  <Ionicons name="arrow-up" size={20} color={colors.white} />
                </TouchableOpacity>
              </View>
              <Text style={styles.disclaimer}>Проверяйте практическое решение по актуальному регламенту применения.</Text>
            </View>
          </>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: 'rgba(7,10,28,0.9)',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 13,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  headerButtonActive: { backgroundColor: colors.primarySoft, borderColor: colors.primaryBright },
  headerCenter: { alignItems: 'center' },
  headerSubtitle: { color: colors.textMuted, fontSize: 9, marginTop: -1 },
  loadingContainer: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  loadingText: { color: colors.textSecondary, marginTop: 12, fontSize: 13 },
  contextBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 16,
    marginTop: 12,
    paddingHorizontal: 13,
    paddingVertical: 10,
    borderRadius: 14,
    backgroundColor: colors.primarySoft,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
  },
  contextBannerCopy: { flex: 1, marginLeft: 9 },
  contextBannerLabel: { color: colors.text, fontSize: 12, fontWeight: '700' },
  contextBannerText: { color: colors.textSecondary, fontSize: 10, marginTop: 2 },
  messages: { flex: 1 },
  messagesContent: { flexGrow: 1, padding: 16, paddingBottom: 22 },
  welcome: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingVertical: 24 },
  aiOrb: {
    width: 62,
    height: 62,
    borderRadius: 21,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    borderWidth: 1,
    borderColor: colors.primaryBright,
    ...shadows.glow,
  },
  welcomeTitle: { color: colors.text, fontSize: 23, fontWeight: '800', marginTop: 18 },
  welcomeText: {
    maxWidth: 380,
    color: colors.textSecondary,
    fontSize: 13,
    lineHeight: 19,
    textAlign: 'center',
    marginTop: 8,
  },
  suggestions: { alignSelf: 'stretch', marginTop: 24, gap: 9 },
  suggestion: {
    minHeight: 49,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 14,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  suggestionText: { flex: 1, color: colors.textSecondary, fontSize: 12, lineHeight: 17, marginRight: 10 },
  messageBubble: {
    maxWidth: '88%',
    paddingHorizontal: 14,
    paddingVertical: 11,
    borderRadius: 16,
    marginBottom: 10,
    borderWidth: 1,
  },
  userMessage: {
    alignSelf: 'flex-end',
    backgroundColor: colors.primary,
    borderColor: colors.primaryBright,
    borderBottomRightRadius: 5,
  },
  assistantMessage: {
    alignSelf: 'flex-start',
    backgroundColor: colors.surface,
    borderColor: colors.borderStrong,
    borderBottomLeftRadius: 5,
  },
  assistantLabel: { flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 6 },
  assistantLabelText: { color: colors.primaryBright, fontSize: 10, fontWeight: '800' },
  messageText: { color: colors.text, fontSize: 14, lineHeight: 21 },
  typingBubble: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  typingText: { color: colors.textSecondary, fontSize: 12 },
  errorBar: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 16,
    marginBottom: 8,
    padding: 10,
    borderRadius: 11,
    backgroundColor: colors.dangerSoft,
    borderWidth: 1,
    borderColor: colors.danger,
  },
  errorText: { flex: 1, color: colors.text, fontSize: 11, marginLeft: 7 },
  composerArea: {
    paddingHorizontal: 14,
    paddingTop: 9,
    paddingBottom: Platform.OS === 'web' ? 12 : 8,
    backgroundColor: 'rgba(17,23,53,0.96)',
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  composer: {
    minHeight: 52,
    maxHeight: 130,
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingLeft: 14,
    paddingRight: 7,
    paddingVertical: 7,
    borderRadius: 17,
    backgroundColor: colors.surfaceElevated,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
  },
  input: {
    flex: 1,
    maxHeight: 105,
    color: colors.text,
    fontSize: 14,
    lineHeight: 20,
    paddingTop: 7,
    paddingBottom: 7,
    outlineStyle: 'none',
  } as any,
  sendButton: {
    width: 38,
    height: 38,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
  },
  sendButtonDisabled: { opacity: 0.4 },
  disclaimer: { color: colors.textMuted, fontSize: 9, textAlign: 'center', marginTop: 6 },
  historyContent: { padding: 16, paddingBottom: 30 },
  historyTitleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  historyTitle: { color: colors.text, fontSize: 21, fontWeight: '800' },
  historySubtitle: { color: colors.textMuted, fontSize: 10, marginTop: 3 },
  historyActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  logoutButton: {
    width: 38,
    height: 38,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 11,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  newChatButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: 11,
    backgroundColor: colors.primary,
  },
  newChatButtonText: { color: colors.white, fontSize: 11, fontWeight: '700' },
  historyCard: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
    padding: 13,
    borderRadius: 15,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  historyCardContent: { flex: 1 },
  historyCardTitle: { color: colors.text, fontSize: 14, fontWeight: '700' },
  historyCardPreview: { color: colors.textSecondary, fontSize: 11, lineHeight: 16, marginTop: 4 },
  historyCardType: { color: colors.primaryBright, fontSize: 9, fontWeight: '700', marginTop: 7 },
  deleteButton: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 9,
    borderRadius: 11,
    backgroundColor: colors.dangerSoft,
  },
  emptyHistory: { alignItems: 'center', paddingVertical: 70 },
  emptyHistoryText: { color: colors.textSecondary, fontSize: 12, marginTop: 12 },
});
