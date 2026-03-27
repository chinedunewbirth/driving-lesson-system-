import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static const _primary = Color(0xFF1565C0); // DriveSmart blue
  // ignore: unused_field
  static const _secondary = Color(0xFF26A69A);

  static ThemeData get light {
    final base = ThemeData(
      useMaterial3: true,
      colorSchemeSeed: _primary,
      brightness: Brightness.light,
    );
    return base.copyWith(
      textTheme: GoogleFonts.poppinsTextTheme(base.textTheme),
      appBarTheme: base.appBarTheme.copyWith(centerTitle: true),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.grey.shade50,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          minimumSize: const Size.fromHeight(50),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }

  static ThemeData get dark {
    final base = ThemeData(
      useMaterial3: true,
      colorSchemeSeed: _primary,
      brightness: Brightness.dark,
    );
    return base.copyWith(
      textTheme: GoogleFonts.poppinsTextTheme(
        base.textTheme,
      ).apply(bodyColor: Colors.white, displayColor: Colors.white),
      appBarTheme: base.appBarTheme.copyWith(centerTitle: true),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          minimumSize: const Size.fromHeight(50),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }
}
