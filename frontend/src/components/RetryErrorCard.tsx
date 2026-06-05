import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface RetryErrorCardProps {
  onRetry: () => void;
  compact?: boolean;
}

export function RetryErrorCard({ onRetry, compact = false }: RetryErrorCardProps) {
  return (
    <View style={[styles.card, compact && styles.compactCard]}>
      <Ionicons name="cloud-offline-outline" size={compact ? 28 : 44} color="#EF4444" />
      <Text style={styles.title}>Не удалось загрузить данные</Text>
      <Text style={styles.message}>Проверьте интернет и нажмите «Повторить».</Text>
      <TouchableOpacity style={styles.retryButton} onPress={onRetry} activeOpacity={0.8}>
        <Text style={styles.retryText}>Повторить</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    margin: 20,
    padding: 20,
    borderRadius: 16,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#FECACA',
    alignItems: 'center',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  compactCard: {
    marginVertical: 12,
    paddingVertical: 18,
  },
  title: {
    marginTop: 10,
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    textAlign: 'center',
  },
  message: {
    marginTop: 6,
    fontSize: 14,
    lineHeight: 20,
    color: '#6B7280',
    textAlign: 'center',
  },
  retryButton: {
    marginTop: 14,
    paddingHorizontal: 18,
    paddingVertical: 10,
    backgroundColor: '#3B82F6',
    borderRadius: 10,
  },
  retryText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
  },
});
