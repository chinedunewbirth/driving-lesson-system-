import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import 'package:intl/intl.dart';

class PaymentsScreen extends StatefulWidget {
  const PaymentsScreen({super.key});

  @override
  State<PaymentsScreen> createState() => _PaymentsScreenState();
}

class _PaymentsScreenState extends State<PaymentsScreen> {
  final _api = ApiService();
  List<dynamic> _payments = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await _api.get('/student/payments');
      _payments = res['payments'] ?? [];
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'completed':
        return Colors.green;
      case 'pending':
        return Colors.orange;
      case 'refunded':
        return Colors.blue;
      default:
        return Colors.red;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payments')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _payments.isEmpty
          ? const Center(child: Text('No payments yet'))
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: _payments.length,
                itemBuilder: (ctx, i) {
                  final p = _payments[i];
                  final date = p['created_at'] != null
                      ? DateFormat.yMMMd().format(
                          DateTime.parse(p['created_at']),
                        )
                      : '';
                  return Card(
                    child: ListTile(
                      leading: CircleAvatar(
                        backgroundColor: _statusColor(
                          p['status'] ?? '',
                        ).withValues(alpha: 0.1),
                        child: Icon(
                          Icons.payment,
                          color: _statusColor(p['status'] ?? ''),
                        ),
                      ),
                      title: Text('£${p['amount'] ?? 0}'),
                      subtitle: Text(
                        '${p['description'] ?? 'Lesson payment'}\n$date',
                      ),
                      isThreeLine: true,
                      trailing: Chip(
                        label: Text(
                          (p['status'] ?? '').toUpperCase(),
                          style: TextStyle(
                            color: _statusColor(p['status'] ?? ''),
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        backgroundColor: _statusColor(
                          p['status'] ?? '',
                        ).withValues(alpha: 0.1),
                        side: BorderSide.none,
                      ),
                    ),
                  );
                },
              ),
            ),
    );
  }
}
