import 'package:flutter/material.dart';

class LessonCard extends StatelessWidget {
  final Map<String, dynamic> lesson;
  final bool showCancel;
  final bool showComplete;
  final VoidCallback? onCancel;
  final VoidCallback? onComplete;

  const LessonCard({
    super.key,
    required this.lesson,
    this.showCancel = false,
    this.showComplete = false,
    this.onCancel,
    this.onComplete,
  });

  Color _statusColor(String status) {
    switch (status) {
      case 'confirmed':
        return Colors.blue;
      case 'completed':
        return Colors.green;
      case 'cancelled':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  IconData _statusIcon(String status) {
    switch (status) {
      case 'confirmed':
        return Icons.event;
      case 'completed':
        return Icons.check_circle;
      case 'cancelled':
        return Icons.cancel;
      default:
        return Icons.help;
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = lesson['status'] ?? '';
    final color = _statusColor(status);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(_statusIcon(status), color: color, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    lesson['instructor_name'] != null
                        ? 'with ${lesson['instructor_name']}'
                        : lesson['student_name'] != null
                        ? 'Student: ${lesson['student_name']}'
                        : 'Lesson #${lesson['id']}',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                Chip(
                  label: Text(
                    status.toUpperCase(),
                    style: TextStyle(
                      color: color,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  backgroundColor: color.withValues(alpha: 0.1),
                  side: BorderSide.none,
                  padding: EdgeInsets.zero,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.calendar_today, size: 16, color: Colors.grey),
                const SizedBox(width: 4),
                Text(lesson['date'] ?? 'N/A'),
                const SizedBox(width: 16),
                const Icon(Icons.access_time, size: 16, color: Colors.grey),
                const SizedBox(width: 4),
                Text(lesson['time'] ?? 'N/A'),
                const SizedBox(width: 16),
                const Icon(Icons.timer, size: 16, color: Colors.grey),
                const SizedBox(width: 4),
                Text('${lesson['duration'] ?? 60} min'),
              ],
            ),
            if (lesson['pickup_address'] != null &&
                lesson['pickup_address'].toString().isNotEmpty) ...[
              const SizedBox(height: 4),
              Row(
                children: [
                  const Icon(Icons.location_on, size: 16, color: Colors.grey),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      lesson['pickup_address'],
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ],
            if (showCancel || showComplete) ...[
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  if (showComplete && status == 'confirmed')
                    TextButton.icon(
                      onPressed: onComplete,
                      icon: const Icon(Icons.check, size: 18),
                      label: const Text('Complete'),
                      style: TextButton.styleFrom(
                        foregroundColor: Colors.green,
                      ),
                    ),
                  if (showCancel && status == 'confirmed')
                    TextButton.icon(
                      onPressed: onCancel,
                      icon: const Icon(Icons.close, size: 18),
                      label: const Text('Cancel'),
                      style: TextButton.styleFrom(foregroundColor: Colors.red),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
