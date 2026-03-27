import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class ProgressScreen extends StatefulWidget {
  const ProgressScreen({super.key});

  @override
  State<ProgressScreen> createState() => _ProgressScreenState();
}

class _ProgressScreenState extends State<ProgressScreen> {
  final _api = ApiService();
  List<dynamic> _skills = [];
  int _progressPercent = 0;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await _api.get('/student/progress');
      _skills = res['skills'] ?? [];
      _progressPercent = res['progress_percent'] ?? 0;
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'mastered':
        return Colors.green;
      case 'confident':
        return Colors.lightGreen;
      case 'developing':
        return Colors.orange;
      case 'introduced':
        return Colors.blue;
      default:
        return Colors.grey;
    }
  }

  IconData _statusIcon(String status) {
    switch (status) {
      case 'mastered':
        return Icons.check_circle;
      case 'confident':
        return Icons.thumb_up;
      case 'developing':
        return Icons.trending_up;
      case 'introduced':
        return Icons.play_circle;
      default:
        return Icons.radio_button_unchecked;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Progress')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  // Progress circle
                  Center(
                    child: SizedBox(
                      width: 140,
                      height: 140,
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          CircularProgressIndicator(
                            value: _progressPercent / 100,
                            strokeWidth: 10,
                            backgroundColor: Colors.grey.shade200,
                            valueColor: const AlwaysStoppedAnimation(
                              Colors.green,
                            ),
                          ),
                          Center(
                            child: Text(
                              '$_progressPercent%',
                              style: Theme.of(context).textTheme.headlineMedium
                                  ?.copyWith(fontWeight: FontWeight.bold),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Center(
                    child: Text(
                      'Skills Mastered',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Skills list
                  ..._skills.map((skill) {
                    final status = skill['status'] ?? 'not_started';
                    return Card(
                      child: ListTile(
                        leading: Icon(
                          _statusIcon(status),
                          color: _statusColor(status),
                        ),
                        title: Text(skill['skill_name'] ?? skill['skill_key']),
                        subtitle: Text(
                          status.replaceAll('_', ' ').toUpperCase(),
                          style: TextStyle(
                            color: _statusColor(status),
                            fontWeight: FontWeight.w600,
                            fontSize: 12,
                          ),
                        ),
                        trailing: skill['notes'] != null
                            ? IconButton(
                                icon: const Icon(Icons.info_outline),
                                onPressed: () => showDialog(
                                  context: context,
                                  builder: (ctx) => AlertDialog(
                                    title: Text(skill['skill_name']),
                                    content: Text(skill['notes']),
                                    actions: [
                                      TextButton(
                                        onPressed: () => Navigator.pop(ctx),
                                        child: const Text('OK'),
                                      ),
                                    ],
                                  ),
                                ),
                              )
                            : null,
                      ),
                    );
                  }),
                ],
              ),
            ),
    );
  }
}
