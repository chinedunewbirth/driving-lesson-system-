import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class ReviewsScreen extends StatefulWidget {
  final int instructorId;
  final String instructorName;

  const ReviewsScreen({
    super.key,
    required this.instructorId,
    required this.instructorName,
  });

  @override
  State<ReviewsScreen> createState() => _ReviewsScreenState();
}

class _ReviewsScreenState extends State<ReviewsScreen> {
  final _api = ApiService();
  List<dynamic> _reviews = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await _api.get('/instructors/${widget.instructorId}/reviews');
      _reviews = res['reviews'] ?? [];
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('${widget.instructorName} Reviews')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _reviews.isEmpty
          ? const Center(child: Text('No reviews yet'))
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _reviews.length,
              itemBuilder: (ctx, i) {
                final r = _reviews[i];
                return Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            ...List.generate(
                              5,
                              (j) => Icon(
                                j < (r['rating'] ?? 0)
                                    ? Icons.star
                                    : Icons.star_border,
                                color: Colors.amber,
                                size: 20,
                              ),
                            ),
                            const Spacer(),
                            Text(
                              r['student_name'] ?? '',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                        if (r['title'] != null && r['title'].isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Text(
                            r['title'],
                            style: Theme.of(context).textTheme.titleSmall
                                ?.copyWith(fontWeight: FontWeight.bold),
                          ),
                        ],
                        if (r['comment'] != null &&
                            r['comment'].isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(r['comment']),
                        ],
                      ],
                    ),
                  ),
                );
              },
            ),
    );
  }
}
