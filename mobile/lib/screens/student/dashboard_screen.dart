import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/lesson_card.dart';
import '../../widgets/stat_card.dart';

class StudentDashboard extends StatefulWidget {
  const StudentDashboard({super.key});

  @override
  State<StudentDashboard> createState() => _StudentDashboardState();
}

class _StudentDashboardState extends State<StudentDashboard> {
  final _api = ApiService();
  Map<String, dynamic>? _data;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      _data = await _api.get('/student/dashboard');
    } on ApiException catch (e) {
      _error = e.message;
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () => Navigator.pushNamed(context, '/notifications'),
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await context.read<AuthProvider>().logout();
              if (!context.mounted) return;
              Navigator.pushReplacementNamed(context, '/login');
            },
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(_error!, style: const TextStyle(color: Colors.red)),
                  const SizedBox(height: 8),
                  ElevatedButton(onPressed: _load, child: const Text('Retry')),
                ],
              ),
            )
          : RefreshIndicator(onRefresh: _load, child: _buildContent()),
      bottomNavigationBar: NavigationBar(
        selectedIndex: 0,
        onDestinationSelected: (i) {
          switch (i) {
            case 1:
              Navigator.pushNamed(context, '/student/book');
              break;
            case 2:
              Navigator.pushNamed(context, '/student/progress');
              break;
            case 3:
              Navigator.pushNamed(context, '/student/payments');
              break;
          }
        },
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home), label: 'Home'),
          NavigationDestination(
            icon: Icon(Icons.add_circle_outline),
            label: 'Book',
          ),
          NavigationDestination(
            icon: Icon(Icons.trending_up),
            label: 'Progress',
          ),
          NavigationDestination(icon: Icon(Icons.payment), label: 'Payments'),
        ],
      ),
    );
  }

  Widget _buildContent() {
    final stats = _data?['stats'] ?? {};
    final upcoming = (_data?['upcoming_lessons'] as List?) ?? [];
    final completed = (_data?['completed_lessons'] as List?) ?? [];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          'Welcome back!',
          style: Theme.of(
            context,
          ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 16),

        // Stats row
        Row(
          children: [
            Expanded(
              child: StatCard(
                label: 'Upcoming',
                value: '${stats['upcoming'] ?? 0}',
                icon: Icons.calendar_today,
                color: Colors.blue,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: StatCard(
                label: 'Completed',
                value: '${stats['completed'] ?? 0}',
                icon: Icons.check_circle,
                color: Colors.green,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: StatCard(
                label: 'Total',
                value: '${stats['total_lessons'] ?? 0}',
                icon: Icons.list,
                color: Colors.orange,
              ),
            ),
          ],
        ),
        const SizedBox(height: 24),

        // Upcoming lessons
        Text(
          'Upcoming Lessons',
          style: Theme.of(
            context,
          ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        if (upcoming.isEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                children: [
                  const Icon(Icons.event_busy, size: 48, color: Colors.grey),
                  const SizedBox(height: 8),
                  const Text('No upcoming lessons'),
                  const SizedBox(height: 8),
                  ElevatedButton(
                    onPressed: () =>
                        Navigator.pushNamed(context, '/student/book'),
                    child: const Text('Book a Lesson'),
                  ),
                ],
              ),
            ),
          )
        else
          ...upcoming.map(
            (l) => LessonCard(
              lesson: l,
              showCancel: true,
              onCancel: () => _cancelLesson(l['id']),
            ),
          ),

        const SizedBox(height: 24),

        // Recent completed
        if (completed.isNotEmpty) ...[
          Text(
            'Recent Completed',
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          ...completed.take(5).map((l) => LessonCard(lesson: l)),
        ],
      ],
    );
  }

  Future<void> _cancelLesson(int lessonId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Cancel Lesson'),
        content: const Text('Are you sure you want to cancel this lesson?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('No'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Yes, cancel'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    try {
      await _api.post('/student/lessons/$lessonId/cancel');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Lesson cancelled'),
          backgroundColor: Colors.green,
        ),
      );
      _load();
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message), backgroundColor: Colors.red),
      );
    }
  }
}
