import React, { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, Platform, StyleSheet, Text, View } from 'react-native';
import { colors, shadows } from '../theme/colors';

interface SplashIntroProps {
  onFinish: () => void;
  duration?: number;
}

export function SplashIntro({ onFinish, duration = 1650 }: SplashIntroProps) {
  const reveal = useRef(new Animated.Value(0)).current;
  const focus = useRef(new Animated.Value(0)).current;
  const exit = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const entrance = Math.max(820, Math.round(duration * 0.62));
    const hold = Math.max(180, Math.round(duration * 0.16));
    const leave = Math.max(260, duration - entrance - hold);

    const animation = Animated.sequence([
      Animated.parallel([
        Animated.timing(reveal, {
          toValue: 1,
          duration: entrance,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
        Animated.timing(focus, {
          toValue: 1,
          duration: entrance + 120,
          easing: Easing.out(Easing.quad),
          useNativeDriver: true,
        }),
      ]),
      Animated.delay(hold),
      Animated.timing(exit, {
        toValue: 1,
        duration: leave,
        easing: Easing.inOut(Easing.quad),
        useNativeDriver: true,
      }),
    ]);

    animation.start(({ finished }) => {
      if (finished) onFinish();
    });

    return () => animation.stop();
  }, [duration, exit, focus, onFinish, reveal]);

  const logoStyle = useMemo(
    () => ({
      opacity: reveal.interpolate({ inputRange: [0, 0.18, 1], outputRange: [0, 0.25, 1] }),
      transform: [
        { scale: reveal.interpolate({ inputRange: [0, 0.45, 1], outputRange: [0.72, 1.08, 1] }) },
        { translateY: reveal.interpolate({ inputRange: [0, 1], outputRange: [14, 0] }) },
      ],
    }),
    [reveal],
  );

  const beamOpacity = focus.interpolate({
    inputRange: [0, 0.3, 0.82, 1],
    outputRange: [0, 0.3, 0.17, 0.05],
  });

  const containerOpacity = exit.interpolate({ inputRange: [0, 1], outputRange: [1, 0] });
  const containerScale = exit.interpolate({ inputRange: [0, 1], outputRange: [1, 1.035] });

  return (
    <Animated.View
      pointerEvents="auto"
      style={[styles.container, { opacity: containerOpacity, transform: [{ scale: containerScale }] }]}
    >
      <View style={styles.orbTop} />
      <View style={styles.orbBottom} />
      <View style={styles.ringOuter} />
      <View style={styles.ringInner} />

      <Animated.View style={[styles.beam, styles.beamLeft, { opacity: beamOpacity }]} />
      <Animated.View style={[styles.beam, styles.beamRight, { opacity: beamOpacity }]} />
      <Animated.View style={[styles.beam, styles.beamTop, { opacity: beamOpacity }]} />

      <Animated.View style={[styles.logoWrap, logoStyle]}>
        <View style={styles.logoGlow} />
        <Text accessibilityRole="header" style={styles.logo}>
          <Text style={styles.logoLight}>b</Text>
          <Text style={styles.logoAccent}>AI</Text>
          <Text style={styles.logoLight}>kov</Text>
        </Text>
        <Text style={styles.caption}>Справочник пестицидов РФ</Text>
      </Animated.View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 999,
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.backgroundDeep,
  },
  orbTop: {
    position: 'absolute',
    width: 420,
    height: 420,
    borderRadius: 210,
    top: -280,
    right: -170,
    backgroundColor: colors.primary,
    opacity: 0.15,
  },
  orbBottom: {
    position: 'absolute',
    width: 360,
    height: 360,
    borderRadius: 180,
    bottom: -250,
    left: -160,
    backgroundColor: colors.cyan,
    opacity: 0.055,
  },
  ringOuter: {
    position: 'absolute',
    width: 320,
    height: 320,
    borderRadius: 160,
    borderWidth: 1,
    borderColor: colors.pattern,
  },
  ringInner: {
    position: 'absolute',
    width: 220,
    height: 220,
    borderRadius: 110,
    borderWidth: 1,
    borderColor: colors.pattern,
  },
  beam: {
    position: 'absolute',
    width: 520,
    height: 120,
    borderRadius: 60,
    backgroundColor: colors.primaryBright,
  },
  beamLeft: {
    left: -390,
    transform: [{ rotate: '-14deg' }],
  },
  beamRight: {
    right: -390,
    transform: [{ rotate: '14deg' }],
  },
  beamTop: {
    top: -80,
    height: 460,
    width: 92,
    transform: [{ rotate: '3deg' }],
  },
  logoWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 34,
    paddingVertical: 26,
    ...shadows.softGlow,
  },
  logoGlow: {
    position: 'absolute',
    width: 220,
    height: 86,
    borderRadius: 44,
    backgroundColor: colors.primaryGlow,
    opacity: Platform.OS === 'web' ? 0.9 : 0.65,
  },
  logo: {
    color: colors.text,
    fontSize: 54,
    fontWeight: '300',
    letterSpacing: -2.2,
    textShadowColor: colors.primaryGlowStrong,
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 22,
  },
  logoLight: {
    color: colors.text,
    fontWeight: '300',
  },
  logoAccent: {
    color: colors.primaryBright,
    fontWeight: '800',
  },
  caption: {
    marginTop: 10,
    color: colors.textMuted,
    fontSize: 12,
    letterSpacing: 1.25,
    textTransform: 'uppercase',
  },
});
