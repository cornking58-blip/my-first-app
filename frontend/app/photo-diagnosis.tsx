import React, { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
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
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { manipulateAsync, SaveFormat } from 'expo-image-manipulator';
import { useRouter } from 'expo-router';
import axios, { isAxiosError } from 'axios';

import { AIAuthGate } from '../src/components/AIAuthGate';
import { AmbientBackground } from '../src/components/AmbientBackground';
import { BrandLogo } from '../src/components/BrandLogo';
import { useAuth } from '../src/auth/AuthContext';
import { colors } from '../src/theme/colors';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type SelectedPhoto = {
  uri: string;
  dataUrl: string;
};

export default function PhotoDiagnosisScreen() {
  const router = useRouter();
  const { loading: authLoading, token, user } = useAuth();
  const [photo, setPhoto] = useState<SelectedPhoto | null>(null);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [error, setError] = useState('');
  const [processing, setProcessing] = useState(false);

  const getErrorText = (requestError: unknown) => {
    if (isAxiosError(requestError)) {
      const detail = requestError.response?.data?.detail;
      if (typeof detail === 'string') return detail;
    }
    return 'Не удалось проанализировать фотографию. Попробуйте ещё раз.';
  };

  const preparePhoto = async (asset: ImagePicker.ImagePickerAsset) => {
    setProcessing(true);
    setError('');
    setAnswer('');
    try {
      const actions = asset.width > 1600 ? [{ resize: { width: 1600 } }] : [];
      const processed = await manipulateAsync(asset.uri, actions, {
        compress: 0.72,
        format: SaveFormat.JPEG,
        base64: true,
      });
      if (!processed.base64) {
        throw new Error('Image base64 is missing');
      }
      setPhoto({
        uri: processed.uri,
        dataUrl: `data:image/jpeg;base64,${processed.base64}`,
      });
    } catch {
      setError('Не удалось подготовить фотографию. Выберите другой снимок.');
    } finally {
      setProcessing(false);
    }
  };

  const pickFromGallery = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('Нет доступа', 'Разрешите доступ к фотографиям в настройках телефона.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: false,
      quality: 1,
    });
    if (!result.canceled && result.assets[0]) {
      await preparePhoto(result.assets[0]);
    }
  };

  const takePhoto = async () => {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('Нет доступа', 'Разрешите доступ к камере в настройках телефона.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ['images'],
      allowsEditing: false,
      quality: 1,
    });
    if (!result.canceled && result.assets[0]) {
      await preparePhoto(result.assets[0]);
    }
  };

  const diagnose = async () => {
    if (!photo || !token || processing) return;
    setProcessing(true);
    setError('');
    setAnswer('');
    try {
      const response = await axios.post(
        `${API_URL}/api/ai/photo-diagnosis`,
        {
          image_data_url: photo.dataUrl,
          question: question.trim() || null,
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setAnswer(String(response.data.answer || '').trim());
    } catch (requestError) {
      setError(getErrorText(requestError));
    } finally {
      setProcessing(false);
    }
  };

  if (authLoading) {
    return (
      <View style={styles.loadingScreen}>
        <ActivityIndicator color={colors.primaryBright} />
      </View>
    );
  }

  if (!user || !token) {
    return <AIAuthGate onBack={() => router.back()} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <AmbientBackground />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={styles.header}>
          <TouchableOpacity style={styles.headerButton} onPress={() => router.back()}>
            <Ionicons name="arrow-back" size={22} color={colors.text} />
          </TouchableOpacity>
          <BrandLogo compact />
          <View style={styles.headerSpacer} />
        </View>

        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.eyebrow}>AI-ФОТОДИАГНОСТИКА</Text>
          <Text style={styles.title}>Покажите, что происходит в поле</Text>
          <Text style={styles.subtitle}>
            Сфотографируйте лист, растение, сорняк или вредителя. bAIkov разберёт видимые признаки и подскажет, что проверить дальше.
          </Text>

          <View style={styles.photoFrame}>
            {photo ? (
              <Image source={{ uri: photo.uri }} style={styles.photo} contentFit="cover" />
            ) : (
              <View style={styles.emptyPhoto}>
                <Ionicons name="scan-outline" size={42} color={colors.primaryBright} />
                <Text style={styles.emptyTitle}>Фотография пока не выбрана</Text>
                <Text style={styles.emptyText}>Лучше крупный план при естественном освещении</Text>
              </View>
            )}
          </View>

          <View style={styles.actionsRow}>
            <TouchableOpacity style={styles.actionButton} onPress={takePhoto} disabled={processing}>
              <Ionicons name="camera-outline" size={20} color={colors.primaryBright} />
              <Text style={styles.actionText}>Снять фото</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionButton} onPress={pickFromGallery} disabled={processing}>
              <Ionicons name="images-outline" size={20} color={colors.primaryBright} />
              <Text style={styles.actionText}>Из галереи</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.inputBlock}>
            <Text style={styles.label}>Что известно? Необязательно</Text>
            <TextInput
              style={styles.input}
              value={question}
              onChangeText={setQuestion}
              placeholder="Например: подсолнечник, 4 пары листьев, после обработки прошло 3 дня"
              placeholderTextColor={colors.textMuted}
              multiline
              maxLength={2000}
              textAlignVertical="top"
            />
          </View>

          <View style={styles.tips}>
            <View style={styles.tipRow}>
              <Ionicons name="checkmark-circle-outline" size={17} color={colors.primaryBright} />
              <Text style={styles.tipText}>Общий вид растения + крупный план симптома</Text>
            </View>
            <View style={styles.tipRow}>
              <Ionicons name="checkmark-circle-outline" size={17} color={colors.primaryBright} />
              <Text style={styles.tipText}>Лицевая и обратная сторона листа</Text>
            </View>
            <View style={styles.tipRow}>
              <Ionicons name="checkmark-circle-outline" size={17} color={colors.primaryBright} />
              <Text style={styles.tipText}>Без сильной тени, грязного объектива и цифрового зума</Text>
            </View>
          </View>

          <TouchableOpacity
            style={[styles.primaryButton, (!photo || processing) && styles.primaryButtonDisabled]}
            onPress={diagnose}
            disabled={!photo || processing}
          >
            {processing ? (
              <ActivityIndicator color={colors.white} />
            ) : (
              <>
                <Ionicons name="sparkles-outline" size={19} color={colors.white} />
                <Text style={styles.primaryButtonText}>Разобрать фотографию</Text>
              </>
            )}
          </TouchableOpacity>

          {error ? (
            <View style={styles.errorBlock}>
              <Ionicons name="alert-circle-outline" size={18} color={colors.danger} />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}

          {answer ? (
            <View style={styles.resultBlock}>
              <View style={styles.resultHeader}>
                <Ionicons name="leaf-outline" size={20} color={colors.primaryBright} />
                <Text style={styles.resultTitle}>Предварительный разбор</Text>
              </View>
              <Text style={styles.resultText}>{answer}</Text>
              <Text style={styles.disclaimer}>
                Фоторазбор помогает сузить круг причин, но не заменяет осмотр поля и проверку регламента.
              </Text>
            </View>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  loadingScreen: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 11,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.background,
  },
  headerButton: {
    width: 40,
    height: 40,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerSpacer: { width: 40 },
  content: {
    width: '100%',
    maxWidth: 720,
    alignSelf: 'center',
    paddingHorizontal: 18,
    paddingTop: 24,
    paddingBottom: 42,
  },
  eyebrow: {
    color: colors.primaryBright,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.8,
  },
  title: {
    color: colors.text,
    fontSize: 28,
    lineHeight: 34,
    fontWeight: '800',
    marginTop: 8,
  },
  subtitle: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 21,
    marginTop: 10,
  },
  photoFrame: {
    width: '100%',
    aspectRatio: 4 / 3,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    overflow: 'hidden',
    marginTop: 22,
    backgroundColor: colors.background,
  },
  photo: { width: '100%', height: '100%' },
  emptyPhoto: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 30,
  },
  emptyTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginTop: 14,
    textAlign: 'center',
  },
  emptyText: {
    color: colors.textMuted,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 6,
    textAlign: 'center',
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 12,
  },
  actionButton: {
    flex: 1,
    minHeight: 48,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  actionText: { color: colors.text, fontSize: 13, fontWeight: '700' },
  inputBlock: { marginTop: 22 },
  label: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 8,
  },
  input: {
    minHeight: 94,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.text,
    backgroundColor: colors.background,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    lineHeight: 20,
  },
  tips: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 14,
    padding: 14,
    gap: 9,
    marginTop: 14,
  },
  tipRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 9 },
  tipText: { flex: 1, color: colors.textSecondary, fontSize: 12, lineHeight: 18 },
  primaryButton: {
    minHeight: 52,
    borderRadius: 14,
    backgroundColor: colors.primary,
    borderWidth: 1,
    borderColor: colors.primaryBright,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 9,
    marginTop: 16,
  },
  primaryButtonDisabled: { opacity: 0.38 },
  primaryButtonText: { color: colors.white, fontSize: 14, fontWeight: '800' },
  errorBlock: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 9,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.danger,
    padding: 13,
    marginTop: 14,
  },
  errorText: { flex: 1, color: colors.danger, fontSize: 13, lineHeight: 19 },
  resultBlock: {
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    padding: 16,
    marginTop: 18,
  },
  resultHeader: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  resultTitle: { color: colors.text, fontSize: 16, fontWeight: '800' },
  resultText: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 22,
    marginTop: 13,
  },
  disclaimer: {
    color: colors.textMuted,
    fontSize: 11,
    lineHeight: 17,
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
});
