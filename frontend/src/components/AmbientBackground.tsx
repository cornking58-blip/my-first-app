import React from 'react';
import { StyleSheet, View } from 'react-native';
import { colors } from '../theme/colors';

export function AmbientBackground() {
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <View style={styles.base} />
      <View style={styles.ringTop} />
      <View style={styles.ringBottom} />
      <View style={styles.lineOne} />
      <View style={styles.lineTwo} />
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: colors.background,
  },
  ringTop: {
    position: 'absolute',
    width: 240,
    height: 240,
    borderRadius: 120,
    borderWidth: 1,
    borderColor: colors.pattern,
    top: -135,
    right: -95,
  },
  ringBottom: {
    position: 'absolute',
    width: 180,
    height: 180,
    borderRadius: 90,
    borderWidth: 1,
    borderColor: colors.pattern,
    bottom: -115,
    left: -90,
  },
  lineOne: {
    position: 'absolute',
    width: 260,
    height: 1,
    backgroundColor: colors.pattern,
    top: 205,
    right: -95,
    transform: [{ rotate: '-28deg' }],
  },
  lineTwo: {
    position: 'absolute',
    width: 220,
    height: 1,
    backgroundColor: colors.pattern,
    bottom: 165,
    left: -85,
    transform: [{ rotate: '24deg' }],
  },
});
