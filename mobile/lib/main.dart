import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'theme.dart';
import 'providers/auth_provider.dart';

// Auth screens
import 'screens/auth/login_screen.dart';
import 'screens/auth/register_screen.dart';

// Student screens
import 'screens/student/dashboard_screen.dart';
import 'screens/student/book_lesson_screen.dart';
import 'screens/student/progress_screen.dart';
import 'screens/student/payments_screen.dart';

// Instructor screens
import 'screens/instructor/dashboard_screen.dart';
import 'screens/instructor/students_screen.dart';
import 'screens/instructor/profile_screen.dart';

// Shared screens
import 'screens/shared/notifications_screen.dart';

void main() {
  runApp(
    ChangeNotifierProvider(
      create: (_) => AuthProvider(),
      child: const DriveSmartApp(),
    ),
  );
}

class DriveSmartApp extends StatelessWidget {
  const DriveSmartApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DriveSmart',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,
      home: const SplashScreen(),
      routes: {
        '/login': (_) => const LoginScreen(),
        '/register': (_) => const RegisterScreen(),
        '/student/dashboard': (_) => const StudentDashboard(),
        '/student/book': (_) => const BookLessonScreen(),
        '/student/progress': (_) => const ProgressScreen(),
        '/student/payments': (_) => const PaymentsScreen(),
        '/instructor/dashboard': (_) => const InstructorDashboard(),
        '/instructor/students': (_) => const StudentsScreen(),
        '/instructor/profile': (_) => const InstructorProfileScreen(),
        '/notifications': (_) => const NotificationsScreen(),
      },
    );
  }
}

/// Shows a splash screen while checking for an existing auth token.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    final auth = context.read<AuthProvider>();
    await auth.tryAutoLogin();
    if (!mounted) return;

    if (auth.isLoggedIn) {
      final route = auth.role == 'instructor'
          ? '/instructor/dashboard'
          : '/student/dashboard';
      Navigator.pushReplacementNamed(context, route);
    } else {
      Navigator.pushReplacementNamed(context, '/login');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.directions_car,
              size: 80,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 16),
            Text(
              'DriveSmart',
              style: Theme.of(
                context,
              ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 24),
            const CircularProgressIndicator(),
          ],
        ),
      ),
    );
  }
}
