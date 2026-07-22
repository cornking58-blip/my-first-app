import React from 'react';
import { StyleSheet, View } from 'react-native';
import { colors } from '../theme/colors';

export function AmbientBackground() {
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <View style={styles.orbTop} />
      <View style={styles.orbSide} />
    </View>
  );
}

const styles = StyleSheet.create({
  orbTop: {
    position: 'absolute',
    width: 310,
    height: 310,
    borderRadius: 155,
    backgroundColor: colors.primary,
    opacity: 0.09,
    top: -190,
    right: -110,
  },
  orbSide: {
    position: 'absolute',
    width: 230,
    height: 230,
    borderRadius: 115,
    backgroundColor: colors.cyan,
    opacity: 0.035,
    top: 300,
    left: -165,
  },
});
