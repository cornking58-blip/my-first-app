import React, { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet, Text, View } from 'react-native';
import { colors } from '../theme/colors';

interface SplashIntroProps {
  onFinish: () => void;
  duration?: number;
}

export function SplashIntro({ onFinish, duration = 1250 }: SplashIntroProps) {
  const reveal = useRef(new Animated.Value(0)).current;
  const pulse = useRef(new Animated.Value(0)).current;
  const exit = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const exitDuration = Math.max(220, duration - 1030);
    const animation = Animated.sequence([
      Animated.timing(reveal, {
        toValue: 1,
        duration: 500,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
      Animated.delay(70),
      Animated.timing(pulse, {
        toValue: 1,
        duration: 180,
        easing: Easing.inOut(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.timing(pulse, {
        toValue: 0,
        duration: 220,
        easing: Easing.inOut(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.delay(60),
      Animated.timing(exit, {
        toValue: 1,
        duration: exitDuration,
        easing: Easing.inOut(Easing.quad),
        useNativeDriver: true,
      }),
    ]);

    animation.start(({ finished }) => {
      if (finished) onFinish();
    });

    return () => animation.stop();
  }, [duration, exit, onFinish, pulse, reveal]);

  const logoScale = reveal.interpolate({
    inputRange: [0, 1],
    outputRange: [0.985, 1],
  });
  const aiScale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.045],
  });
  const glowOpacity = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 0.42],
  });
  const glowScale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.82, 1.2],
  });
  const containerOpacity = exit.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 0],
  });

  return (
    <Animated.View
      pointerEvents="auto"
      style={[styles.container, { opacity: containerOpacity }]}
    >
      <Animated.View
        accessible
        accessibilityRole="header"
        accessibilityLabel="bAIkov"
        style={[
          styles.logoRow,
          {
            opacity: reveal,
            transform: [{ scale: logoScale }],
          },
        ]}
      >
        <Text style={styles.logoLight}>b</Text>
        <View style={styles.aiWrap}>
          <Animated.View
            pointerEvents="none"
            style={[
              styles.aiGlow,
              {
                opacity: glowOpacity,
                transform: [{ scale: glowScale }],
              },
            ]}
          />
          <Animated.Text style={[styles.logoAccent, { transform: [{ scale: aiScale }] }]}>AI</Animated.Text>
        </View>
        <Text style={styles.logoLight}>kov</Text>
      </Animated.View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 999,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#000000',
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoLight: {
    color: colors.text,
    fontSize: 54,
    lineHeight: 64,
    fontWeight: '300',
    letterSpacing: -2.2,
  },
  aiWrap: {
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
  aiGlow: {
    position: 'absolute',
    width: 76,
    height: 42,
    borderRadius: 21,
    backgroundColor: colors.primaryBright,
  },
  logoAccent: {
    color: colors.primaryBright,
    fontSize: 54,
    lineHeight: 64,
    fontWeight: '800',
    letterSpacing: -2.2,
    textShadowColor: colors.primaryGlowStrong,
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 10,
  },
});
