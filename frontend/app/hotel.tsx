import React, { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Dimensions,
  Linking,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

const { width } = Dimensions.get('window');

const ROOMS = [
  {
    id: 1,
    name: 'Стандарт с видом на море',
    price: '4 900',
    area: '24 м²',
    guests: 2,
    icon: 'bed-outline' as const,
    features: ['Вид на море', 'Кондиционер', 'Wi-Fi', 'Балкон'],
  },
  {
    id: 2,
    name: 'Делюкс',
    price: '7 500',
    area: '36 м²',
    guests: 2,
    icon: 'star-outline' as const,
    features: ['Панорамный вид', 'Джакузи', 'Мини-бар', 'Терраса'],
    highlight: true,
  },
  {
    id: 3,
    name: 'Семейный люкс',
    price: '11 200',
    area: '52 м²',
    guests: 4,
    icon: 'people-outline' as const,
    features: ['2 спальни', 'Кухня', 'Гостиная', 'Вид на море'],
  },
];

const AMENITIES = [
  { icon: 'water-outline' as const, label: 'Бассейн\nна берегу' },
  { icon: 'restaurant-outline' as const, label: 'Ресторан\nчерноморской кухни' },
  { icon: 'fitness-outline' as const, label: 'Фитнес\nцентр' },
  { icon: 'body-outline' as const, label: 'Спа &\nМассаж' },
  { icon: 'boat-outline' as const, label: 'Прокат\nлодок' },
  { icon: 'wine-outline' as const, label: 'Бар\nна пляже' },
];

const REVIEWS = [
  {
    id: 1,
    name: 'Анна К.',
    rating: 5,
    text: 'Невероятный отдых! Номер с видом на море — это настоящее счастье. Персонал очень внимательный.',
    date: 'Август 2025',
  },
  {
    id: 2,
    name: 'Михаил Р.',
    rating: 5,
    text: 'Лучший отель на побережье. Рыбный ресторан просто шедевр — свежайшие блюда каждый день.',
    date: 'Июль 2025',
  },
  {
    id: 3,
    name: 'Елена В.',
    rating: 4,
    text: 'Отличный сервис, красивая территория, прямой выход к морю. Обязательно вернёмся!',
    date: 'Сентябрь 2025',
  },
];

const StarRating = ({ rating }: { rating: number }) => (
  <View style={styles.starsRow}>
    {[1, 2, 3, 4, 5].map((s) => (
      <Ionicons
        key={s}
        name={s <= rating ? 'star' : 'star-outline'}
        size={14}
        color={s <= rating ? '#F59E0B' : '#D1D5DB'}
        style={{ marginRight: 2 }}
      />
    ))}
  </View>
);

export default function HotelLandingScreen() {
  const [checkIn, setCheckIn] = useState('');
  const [checkOut, setCheckOut] = useState('');

  const handleBooking = () => {
    Linking.openURL('tel:+78001234567');
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false}>

        {/* ─── HERO ─── */}
        <View style={styles.hero}>
          {/* Sea gradient background */}
          <View style={[styles.heroGradient, { backgroundColor: '#0369A1' }]} />
          {/* Wave decoration */}
          <View style={styles.heroWave} />

          <View style={styles.heroContent}>
            <View style={styles.heroBadge}>
              <Ionicons name="star" size={12} color="#F59E0B" />
              <Text style={styles.heroBadgeText}>5 звёзд · Черноморское побережье</Text>
            </View>
            <Text style={styles.heroTitle}>Лазурный{'\n'}Берег</Text>
            <Text style={styles.heroSubtitle}>
              Роскошный отдых у моря — там, где горы{'\n'}встречаются с волнами
            </Text>

            {/* Quick booking strip */}
            <View style={styles.bookingStrip}>
              <View style={styles.bookingField}>
                <Ionicons name="calendar-outline" size={16} color="#0369A1" />
                <Text style={styles.bookingLabel}>Заезд</Text>
                <Text style={styles.bookingValue}>Выбрать</Text>
              </View>
              <View style={styles.bookingDivider} />
              <View style={styles.bookingField}>
                <Ionicons name="calendar-outline" size={16} color="#0369A1" />
                <Text style={styles.bookingLabel}>Выезд</Text>
                <Text style={styles.bookingValue}>Выбрать</Text>
              </View>
              <TouchableOpacity style={styles.bookingButton} onPress={handleBooking}>
                <Text style={styles.bookingButtonText}>Найти</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>

        {/* ─── STATS BAR ─── */}
        <View style={styles.statsBar}>
          {[
            { value: '15+', label: 'лет опыта' },
            { value: '4.9', label: 'рейтинг' },
            { value: '300м', label: 'до моря' },
            { value: '12k+', label: 'гостей' },
          ].map((stat, i) => (
            <View key={i} style={styles.statCell}>
              <Text style={styles.statValue}>{stat.value}</Text>
              <Text style={styles.statLabel}>{stat.label}</Text>
            </View>
          ))}
        </View>

        {/* ─── ABOUT ─── */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <View style={styles.sectionAccent} />
            <Text style={styles.sectionTitle}>Об отеле</Text>
          </View>
          <Text style={styles.aboutText}>
            Отель «Лазурный Берег» расположен в живописном уголке Черноморского побережья,
            всего в 300 метрах от кристально чистого моря. Мы предлагаем 120 комфортабельных
            номеров с видом на море или горы, ресторан с блюдами местной кухни,
            открытый бассейн с морской водой и собственный пляж с сервисом.
          </Text>
          <View style={styles.featureList}>
            {[
              'Собственный пляж с шезлонгами',
              'Бесплатная парковка',
              'Трансфер из аэропорта',
              'Анимация для детей',
            ].map((f, i) => (
              <View key={i} style={styles.featureItem}>
                <Ionicons name="checkmark-circle" size={18} color="#10B981" />
                <Text style={styles.featureText}>{f}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* ─── AMENITIES ─── */}
        <View style={[styles.section, styles.sectionGray]}>
          <View style={styles.sectionHeader}>
            <View style={styles.sectionAccent} />
            <Text style={styles.sectionTitle}>Удобства</Text>
          </View>
          <View style={styles.amenitiesGrid}>
            {AMENITIES.map((a, i) => (
              <View key={i} style={styles.amenityCard}>
                <View style={styles.amenityIconWrap}>
                  <Ionicons name={a.icon} size={28} color="#0369A1" />
                </View>
                <Text style={styles.amenityLabel}>{a.label}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* ─── ROOMS ─── */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <View style={styles.sectionAccent} />
            <Text style={styles.sectionTitle}>Номера</Text>
          </View>
          {ROOMS.map((room) => (
            <View
              key={room.id}
              style={[styles.roomCard, room.highlight && styles.roomCardHighlight]}
            >
              {room.highlight && (
                <View style={styles.roomBadge}>
                  <Text style={styles.roomBadgeText}>Популярный</Text>
                </View>
              )}
              <View style={styles.roomHeader}>
                <View style={[styles.roomIconWrap, room.highlight && styles.roomIconWrapHL]}>
                  <Ionicons
                    name={room.icon}
                    size={24}
                    color={room.highlight ? '#FFFFFF' : '#0369A1'}
                  />
                </View>
                <View style={styles.roomInfo}>
                  <Text style={styles.roomName}>{room.name}</Text>
                  <View style={styles.roomMeta}>
                    <Ionicons name="resize-outline" size={14} color="#6B7280" />
                    <Text style={styles.roomMetaText}>{room.area}</Text>
                    <Ionicons name="person-outline" size={14} color="#6B7280" style={{ marginLeft: 8 }} />
                    <Text style={styles.roomMetaText}>{room.guests} гостей</Text>
                  </View>
                </View>
                <View>
                  <Text style={styles.roomPrice}>₽{room.price}</Text>
                  <Text style={styles.roomPriceLabel}>/ ночь</Text>
                </View>
              </View>
              <View style={styles.roomFeatures}>
                {room.features.map((f, i) => (
                  <View key={i} style={styles.roomFeaturePill}>
                    <Text style={styles.roomFeaturePillText}>{f}</Text>
                  </View>
                ))}
              </View>
              <TouchableOpacity
                style={[styles.roomBookBtn, room.highlight && styles.roomBookBtnHL]}
                onPress={handleBooking}
              >
                <Text style={[styles.roomBookBtnText, room.highlight && styles.roomBookBtnTextHL]}>
                  Забронировать
                </Text>
                <Ionicons
                  name="arrow-forward"
                  size={16}
                  color={room.highlight ? '#FFFFFF' : '#0369A1'}
                />
              </TouchableOpacity>
            </View>
          ))}
        </View>

        {/* ─── BEACH SECTION ─── */}
        <View style={styles.beachSection}>
          <View style={[StyleSheet.absoluteFill, { backgroundColor: '#0C4A6E' }]} />
          <View style={styles.beachContent}>
            <Ionicons name="sunny" size={40} color="#FCD34D" />
            <Text style={styles.beachTitle}>Собственный пляж</Text>
            <Text style={styles.beachText}>
              350 метров золотого песка только для гостей отеля.
              Шезлонги, зонтики, бар и водные развлечения включены в стоимость проживания.
            </Text>
            <View style={styles.beachStats}>
              {[
                { icon: 'thermometer-outline' as const, value: '+26°C', label: 'вода' },
                { icon: 'sunny-outline' as const, value: '280', label: 'солнечных дней' },
                { icon: 'time-outline' as const, value: '7:00–21:00', label: 'пляж открыт' },
              ].map((s, i) => (
                <View key={i} style={styles.beachStat}>
                  <Ionicons name={s.icon} size={20} color="#7DD3FC" />
                  <Text style={styles.beachStatValue}>{s.value}</Text>
                  <Text style={styles.beachStatLabel}>{s.label}</Text>
                </View>
              ))}
            </View>
          </View>
        </View>

        {/* ─── REVIEWS ─── */}
        <View style={[styles.section, styles.sectionGray]}>
          <View style={styles.sectionHeader}>
            <View style={styles.sectionAccent} />
            <Text style={styles.sectionTitle}>Отзывы гостей</Text>
          </View>
          {REVIEWS.map((review) => (
            <View key={review.id} style={styles.reviewCard}>
              <View style={styles.reviewTop}>
                <View style={styles.reviewAvatar}>
                  <Text style={styles.reviewAvatarText}>{review.name[0]}</Text>
                </View>
                <View style={styles.reviewMeta}>
                  <Text style={styles.reviewName}>{review.name}</Text>
                  <StarRating rating={review.rating} />
                </View>
                <Text style={styles.reviewDate}>{review.date}</Text>
              </View>
              <Text style={styles.reviewText}>{review.text}</Text>
            </View>
          ))}
        </View>

        {/* ─── CTA / CONTACT ─── */}
        <View style={styles.ctaSection}>
          <View style={[StyleSheet.absoluteFill, { backgroundColor: '#0369A1' }]} />
          <View style={styles.ctaContent}>
            <Text style={styles.ctaTitle}>Готовы к отдыху?</Text>
            <Text style={styles.ctaSubtitle}>
              Свяжитесь с нами и мы подберём идеальный номер
            </Text>
            <TouchableOpacity style={styles.ctaPhone} onPress={handleBooking}>
              <Ionicons name="call-outline" size={20} color="#0369A1" />
              <Text style={styles.ctaPhoneText}>+7 (800) 123-45-67</Text>
            </TouchableOpacity>
            <Text style={styles.ctaNote}>Бесплатный звонок · 24/7</Text>

            <View style={styles.ctaSocials}>
              {(['logo-instagram', 'logo-vk', 'logo-telegram'] as const).map((icon, i) => (
                <TouchableOpacity key={i} style={styles.ctaSocialBtn}>
                  <Ionicons name={icon} size={22} color="#FFFFFF" />
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </View>

        {/* ─── FOOTER ─── */}
        <View style={styles.footer}>
          <Text style={styles.footerLogo}>Лазурный Берег</Text>
          <Text style={styles.footerAddress}>
            г. Геленджик, ул. Морская, 42, Краснодарский край
          </Text>
          <Text style={styles.footerCopy}>© 2026 Отель «Лазурный Берег». Все права защищены.</Text>
        </View>

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },

  // HERO
  hero: { height: 520, overflow: 'hidden' },
  heroGradient: { ...StyleSheet.absoluteFillObject },
  heroWave: {
    position: 'absolute',
    bottom: -2,
    left: 0,
    right: 0,
    height: 60,
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 40,
    borderTopRightRadius: 40,
  },
  heroContent: { flex: 1, paddingHorizontal: 24, paddingTop: 40, paddingBottom: 80 },
  heroBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    marginBottom: 16,
  },
  heroBadgeText: { color: '#FFFFFF', fontSize: 13, fontWeight: '600', marginLeft: 6 },
  heroTitle: {
    fontSize: 52,
    fontWeight: '900',
    color: '#FFFFFF',
    lineHeight: 56,
    letterSpacing: -1,
    marginBottom: 12,
  },
  heroSubtitle: { fontSize: 16, color: 'rgba(255,255,255,0.85)', lineHeight: 24, marginBottom: 28 },
  bookingStrip: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 8,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 8,
  },
  bookingField: { flex: 1, alignItems: 'center', paddingVertical: 6 },
  bookingLabel: { fontSize: 11, color: '#9CA3AF', marginTop: 4 },
  bookingValue: { fontSize: 14, fontWeight: '600', color: '#111827' },
  bookingDivider: { width: 1, height: 36, backgroundColor: '#E5E7EB' },
  bookingButton: {
    backgroundColor: '#0369A1',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
    marginLeft: 8,
  },
  bookingButtonText: { color: '#FFFFFF', fontWeight: '700', fontSize: 14 },

  // STATS
  statsBar: {
    flexDirection: 'row',
    backgroundColor: '#F0F9FF',
    paddingVertical: 20,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#BAE6FD',
  },
  statCell: { flex: 1, alignItems: 'center' },
  statValue: { fontSize: 22, fontWeight: '800', color: '#0369A1' },
  statLabel: { fontSize: 12, color: '#64748B', marginTop: 2 },

  // SECTION
  section: { paddingHorizontal: 20, paddingVertical: 28 },
  sectionGray: { backgroundColor: '#F8FAFC' },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 16 },
  sectionAccent: {
    width: 4,
    height: 22,
    backgroundColor: '#0369A1',
    borderRadius: 2,
    marginRight: 10,
  },
  sectionTitle: { fontSize: 22, fontWeight: '800', color: '#0F172A' },

  // ABOUT
  aboutText: { fontSize: 15, color: '#475569', lineHeight: 24, marginBottom: 16 },
  featureList: { gap: 10 },
  featureItem: { flexDirection: 'row', alignItems: 'center' },
  featureText: { fontSize: 15, color: '#334155', marginLeft: 10 },

  // AMENITIES
  amenitiesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  amenityCard: {
    width: (width - 64) / 3,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    alignItems: 'center',
    shadowColor: '#0369A1',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  amenityIconWrap: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#E0F2FE',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  amenityLabel: {
    fontSize: 12,
    color: '#334155',
    textAlign: 'center',
    lineHeight: 17,
    fontWeight: '500',
  },

  // ROOMS
  roomCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 18,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 3,
  },
  roomCardHighlight: {
    borderColor: '#0369A1',
    borderWidth: 2,
    backgroundColor: '#F0F9FF',
  },
  roomBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#0369A1',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    marginBottom: 10,
  },
  roomBadgeText: { color: '#FFFFFF', fontSize: 11, fontWeight: '700' },
  roomHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  roomIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 14,
    backgroundColor: '#E0F2FE',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  roomIconWrapHL: { backgroundColor: '#0369A1' },
  roomInfo: { flex: 1 },
  roomName: { fontSize: 16, fontWeight: '700', color: '#0F172A', marginBottom: 4 },
  roomMeta: { flexDirection: 'row', alignItems: 'center' },
  roomMetaText: { fontSize: 13, color: '#6B7280', marginLeft: 4 },
  roomPrice: { fontSize: 20, fontWeight: '800', color: '#0369A1', textAlign: 'right' },
  roomPriceLabel: { fontSize: 12, color: '#94A3B8', textAlign: 'right' },
  roomFeatures: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 14 },
  roomFeaturePill: {
    backgroundColor: '#F1F5F9',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
  },
  roomFeaturePillText: { fontSize: 12, color: '#475569', fontWeight: '500' },
  roomBookBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: '#0369A1',
    borderRadius: 12,
    paddingVertical: 12,
    gap: 6,
  },
  roomBookBtnHL: { backgroundColor: '#0369A1', borderColor: '#0369A1' },
  roomBookBtnText: { fontSize: 15, fontWeight: '700', color: '#0369A1' },
  roomBookBtnTextHL: { color: '#FFFFFF' },

  // BEACH
  beachSection: { overflow: 'hidden' },
  beachContent: {
    paddingHorizontal: 24,
    paddingVertical: 40,
    alignItems: 'center',
  },
  beachTitle: {
    fontSize: 28,
    fontWeight: '800',
    color: '#FFFFFF',
    marginTop: 12,
    marginBottom: 10,
  },
  beachText: {
    fontSize: 15,
    color: 'rgba(255,255,255,0.8)',
    textAlign: 'center',
    lineHeight: 23,
    marginBottom: 24,
  },
  beachStats: { flexDirection: 'row', gap: 24 },
  beachStat: { alignItems: 'center' },
  beachStatValue: {
    fontSize: 18,
    fontWeight: '800',
    color: '#FFFFFF',
    marginTop: 6,
    marginBottom: 2,
  },
  beachStatLabel: { fontSize: 12, color: 'rgba(255,255,255,0.7)' },

  // REVIEWS
  starsRow: { flexDirection: 'row', marginTop: 2 },
  reviewCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 2,
  },
  reviewTop: { flexDirection: 'row', alignItems: 'center', marginBottom: 10 },
  reviewAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#0369A1',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  reviewAvatarText: { color: '#FFFFFF', fontWeight: '700', fontSize: 16 },
  reviewMeta: { flex: 1 },
  reviewName: { fontSize: 15, fontWeight: '700', color: '#0F172A' },
  reviewDate: { fontSize: 12, color: '#94A3B8' },
  reviewText: { fontSize: 14, color: '#475569', lineHeight: 22 },

  // CTA
  ctaSection: { overflow: 'hidden' },
  ctaContent: { paddingHorizontal: 24, paddingVertical: 44, alignItems: 'center' },
  ctaTitle: {
    fontSize: 30,
    fontWeight: '900',
    color: '#FFFFFF',
    marginBottom: 8,
    textAlign: 'center',
  },
  ctaSubtitle: {
    fontSize: 15,
    color: 'rgba(255,255,255,0.8)',
    textAlign: 'center',
    marginBottom: 24,
  },
  ctaPhone: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 14,
    gap: 8,
    marginBottom: 8,
  },
  ctaPhoneText: { fontSize: 18, fontWeight: '800', color: '#0369A1' },
  ctaNote: { fontSize: 12, color: 'rgba(255,255,255,0.7)', marginBottom: 24 },
  ctaSocials: { flexDirection: 'row', gap: 12 },
  ctaSocialBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },

  // FOOTER
  footer: {
    backgroundColor: '#0F172A',
    paddingHorizontal: 24,
    paddingVertical: 28,
    alignItems: 'center',
  },
  footerLogo: {
    fontSize: 20,
    fontWeight: '800',
    color: '#FFFFFF',
    marginBottom: 8,
    letterSpacing: 0.5,
  },
  footerAddress: { fontSize: 13, color: '#94A3B8', textAlign: 'center', marginBottom: 6 },
  footerCopy: { fontSize: 12, color: '#475569', textAlign: 'center' },
});
