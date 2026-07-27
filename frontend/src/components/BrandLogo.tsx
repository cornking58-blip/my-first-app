import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors } from '../theme/colors';

interface BrandLogoProps {
  compact?: boolean;
}

export function BrandLogo({ compact = false }: BrandLogoProps) {
  return (
    <View style={styles.wrap}>
      <View pointerEvents="none" style={styles.glow} />
      <Text style={[styles.logo, compact && styles.logoCompact]}>
        <Text style={styles.light}>b</Text>
        <Text style={styles.accent}>AI</Text>
        <Text style={styles.light}>kov</Text>
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignSelf: 'flex-start',
    justifyContent: 'center',
  },
  glow: {
    position: 'absolute',
    left: 10,
    right: 10,
    height: 22,
    borderRadius: 14,
    backgroundColor: colors.primaryGlow,
  },
  logo: {
    color: colors.text,
    fontSize: 30,
    fontWeight: '300',
    letterSpacing: -1.1,
    textShadowColor: colors.primaryGlowStrong,
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 10,
  },
  logoCompact: {
    fontSize: 24,
  },
  light: {
    color: colors.text,
    fontWeight: '300',
  },
  accent: {
    color: colors.primaryBright,
    fontWeight: '700',
  },
});
