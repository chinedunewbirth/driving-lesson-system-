import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import 'package:intl/intl.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final _api = ApiService();
  List<dynamic> _notifications = [];
  int _unreadCount = 0;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await _api.get('/notifications');
      _notifications = res['notifications'] ?? [];
      _unreadCount = res['unread_count'] ?? 0;
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _markRead(int id) async {
    try {
      await _api.post('/notifications/$id/read');
      _load();
    } catch (_) {}
  }

  IconData _categoryIcon(String? category) {
    switch (category) {
      case 'success':
        return Icons.check_circle;
      case 'warning':
        return Icons.warning;
      case 'danger':
        return Icons.error;
      default:
        return Icons.info;
    }
  }

  Color _categoryColor(String? category) {
    switch (category) {
      case 'success':
        return Colors.green;
      case 'warning':
        return Colors.orange;
      case 'danger':
        return Colors.red;
      default:
        return Colors.blue;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          'Notifications${_unreadCount > 0 ? ' ($_unreadCount)' : ''}',
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _notifications.isEmpty
          ? const Center(child: Text('No notifications'))
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView.builder(
                padding: const EdgeInsets.all(8),
                itemCount: _notifications.length,
                itemBuilder: (ctx, i) {
                  final n = _notifications[i];
                  final isRead = n['is_read'] == true;
                  final cat = n['category'];
                  final date = n['created_at'] != null
                      ? DateFormat.yMMMd().add_jm().format(
                          DateTime.parse(n['created_at']),
                        )
                      : '';

                  return Card(
                    color: isRead
                        ? null
                        : Theme.of(
                            context,
                          ).colorScheme.primaryContainer.withValues(alpha: 0.3),
                    child: ListTile(
                      leading: Icon(
                        _categoryIcon(cat),
                        color: _categoryColor(cat),
                      ),
                      title: Text(
                        n['title'] ?? '',
                        style: TextStyle(
                          fontWeight: isRead
                              ? FontWeight.normal
                              : FontWeight.bold,
                        ),
                      ),
                      subtitle: Text('${n['message'] ?? ''}\n$date'),
                      isThreeLine: true,
                      trailing: !isRead
                          ? IconButton(
                              icon: const Icon(Icons.mark_email_read),
                              onPressed: () => _markRead(n['id']),
                            )
                          : null,
                    ),
                  );
                },
              ),
            ),
    );
  }
}
