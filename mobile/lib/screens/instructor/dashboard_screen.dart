import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/lesson_card.dart';
import '../../widgets/stat_card.dart';

class InstructorDashboard extends StatefulWidget {
  const InstructorDashboard({super.key});

  @override
  State<InstructorDashboard> createState() => _InstructorDashboardState();
}

class _InstructorDashboardState extends State<InstructorDashboard> {
  final _api = ApiService();
  Map<String, dynamic>? _data;
  bool _loading = true;
  String? _error;
  final int _navIndex = 0;

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
      _data = await _api.get('/instructor/dashboard');
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
        title: const Text('Instructor Dashboard'),
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
        selectedIndex: _navIndex,
        onDestinationSelected: (i) {
          if (i == _navIndex) return;
          switch (i) {
            case 1:
              Navigator.pushNamed(context, '/instructor/students');
              break;
            case 2:
              Navigator.pushNamed(context, '/instructor/profile');
              break;
          }
          // Don't update index for push-navigated tabs
        },
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.people), label: 'Students'),
          NavigationDestination(icon: Icon(Icons.person), label: 'Profile'),
        ],
      ),
    );
  }

  Widget _buildContent() {
    final stats = _data?['stats'] ?? {};
    final lessons = (_data?['lessons'] as List?) ?? [];
    final confirmed = lessons.where((l) => l['status'] == 'confirmed').toList();
    final completed = lessons.where((l) => l['status'] == 'completed').toList();

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Stats
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            SizedBox(
              width: (MediaQuery.of(context).size.width - 44) / 2,
              child: StatCard(
                label: 'Revenue',
                value: '£${stats['total_revenue'] ?? 0}',
                icon: Icons.attach_money,
                color: Colors.green,
              ),
            ),
            SizedBox(
              width: (MediaQuery.of(context).size.width - 44) / 2,
              child: StatCard(
                label: 'Students',
                value: '${stats['unique_students'] ?? 0}',
                icon: Icons.people,
                color: Colors.blue,
              ),
            ),
            SizedBox(
              width: (MediaQuery.of(context).size.width - 44) / 2,
              child: StatCard(
                label: 'Upcoming',
                value: '${stats['confirmed'] ?? 0}',
                icon: Icons.calendar_today,
                color: Colors.orange,
              ),
            ),
            SizedBox(
              width: (MediaQuery.of(context).size.width - 44) / 2,
              child: StatCard(
                label: 'Completed',
                value: '${stats['completed'] ?? 0}',
                icon: Icons.check_circle,
                color: Colors.teal,
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
        if (confirmed.isEmpty)
          const Card(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: Text('No upcoming lessons')),
            ),
          )
        else
          ...confirmed.map(
            (l) => LessonCard(
              lesson: l,
              showComplete: true,
              showCancel: true,
              onComplete: () => _completeLesson(l['id']),
              onCancel: () => _cancelLesson(l['id']),
            ),
          ),

        if (completed.isNotEmpty) ...[
          const SizedBox(height: 24),
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

  Future<void> _completeLesson(int id) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Complete Lesson'),
        content: const Text('Mark this lesson as completed?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('No'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Yes'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await _api.post('/instructor/lessons/$id/complete');
      _load();
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message), backgroundColor: Colors.red),
      );
    }
  }

  Future<void> _cancelLesson(int id) async {
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
      await _api.post('/instructor/lessons/$id/cancel');
      _load();
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message), backgroundColor: Colors.red),
      );
    }
  }
}
