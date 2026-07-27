import React from 'react';
import { StyleSheet, View } from 'react-native';
import { colors } from '../theme/colors';

export function AmbientBackground() {
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <View style={styles.deepShade} />
      <View style={styles.orbTop} />
      <View style={styles.orbSide} />
      <View style={styles.orbBottom} />
      <View style={styles.ringTop} />
      <View style={styles.ringSide} />
      <View style={styles.lineOne} />
      <View style={styles.lineTwo} />
      <View style={styles.diamond} />
    </View>
  );
}

const styles = StyleSheet.create({
  deepShade: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: colors.background,
  },
  orbTop: {
    position: 'absolute',
    width: 360,
    height: 360,
    borderRadius: 180,
    backgroundColor: colors.primary,
    opacity: 0.11,
    top: -235,
    right: -125,
  },
  orbSide: {
    position: 'absolute',
    width: 260,
    height: 260,
    borderRadius: 130,
    backgroundColor: colors.cyan,
    opacity: 0.045,
    top: 280,
    left: -190,
  },
  orbBottom: {
    position: 'absolute',
    width: 320,
    height: 320,
    borderRadius: 160,
    backgroundColor: colors.primaryBright,
    opacity: 0.045,
    bottom: -230,
    right: -130,
  },
  ringTop: {
    position: 'absolute',
    width: 205,
    height: 205,
    borderRadius: 103,
    borderWidth: 1,
    borderColor: colors.pattern,
    top: -70,
    right: -48,
  },
  ringSide: {
    position: 'absolute',
    width: 150,
    height: 150,
    borderRadius: 75,
    borderWidth: 1,
    borderColor: colors.pattern,
    top: 410,
    left: -82,
  },
  lineOne: {
    position: 'absolute',
    width: 260,
    height: 1,
    backgroundColor: colors.pattern,
    top: 215,
    right: -75,
    transform: [{ rotate: '-32deg' }],
  },
  lineTwo: {
    position: 'absolute',
    width: 220,
    height: 1,
    backgroundColor: colors.pattern,
    bottom: 170,
    left: -70,
    transform: [{ rotate: '28deg' }],
  },
  diamond: {
    position: 'absolute',
    width: 72,
    height: 72,
    borderWidth: 1,
    borderColor: colors.pattern,
    top: '42%',
    right: -38,
    transform: [{ rotate: '45deg' }],
  },
});
