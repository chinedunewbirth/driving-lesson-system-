import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class StudentsScreen extends StatefulWidget {
  const StudentsScreen({super.key});

  @override
  State<StudentsScreen> createState() => _StudentsScreenState();
}

class _StudentsScreenState extends State<StudentsScreen> {
  final _api = ApiService();
  List<dynamic> _students = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await _api.get('/instructor/students');
      _students = res['students'] ?? [];
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Students')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _students.isEmpty
          ? const Center(child: Text('No students yet'))
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: _students.length,
                itemBuilder: (ctx, i) {
                  final s = _students[i];
                  return Card(
                    child: ListTile(
                      leading: CircleAvatar(
                        child: Text((s['username'] ?? '?')[0].toUpperCase()),
                      ),
                      title: Text(s['username'] ?? ''),
                      subtitle: Text(
                        '${s['completed_lessons']} / ${s['total_lessons']} lessons completed',
                      ),
                      trailing: const Icon(Icons.chevron_right),
                    ),
                  );
                },
              ),
            ),
    );
  }
}
