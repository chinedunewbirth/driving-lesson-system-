import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import 'package:intl/intl.dart';

class BookLessonScreen extends StatefulWidget {
  const BookLessonScreen({super.key});

  @override
  State<BookLessonScreen> createState() => _BookLessonScreenState();
}

class _BookLessonScreenState extends State<BookLessonScreen> {
  final _api = ApiService();
  List<dynamic> _instructors = [];
  bool _loading = true;

  int? _selectedInstructorId;
  DateTime? _selectedDate;
  TimeOfDay? _selectedTime;
  int _duration = 60;
  final _pickupCtrl = TextEditingController();
  bool _booking = false;

  @override
  void initState() {
    super.initState();
    _loadInstructors();
  }

  Future<void> _loadInstructors() async {
    try {
      final res = await _api.get('/instructors');
      _instructors = res['instructors'] ?? [];
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final date = await showDatePicker(
      context: context,
      initialDate: now.add(const Duration(days: 1)),
      firstDate: now,
      lastDate: now.add(const Duration(days: 90)),
    );
    if (date != null) setState(() => _selectedDate = date);
  }

  Future<void> _pickTime() async {
    final time = await showTimePicker(
      context: context,
      initialTime: const TimeOfDay(hour: 9, minute: 0),
    );
    if (time != null) setState(() => _selectedTime = time);
  }

  Future<void> _book() async {
    if (_selectedInstructorId == null ||
        _selectedDate == null ||
        _selectedTime == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Select instructor, date and time'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    setState(() => _booking = true);
    try {
      final dateStr = DateFormat('yyyy-MM-dd').format(_selectedDate!);
      final timeStr =
          '${_selectedTime!.hour.toString().padLeft(2, '0')}:${_selectedTime!.minute.toString().padLeft(2, '0')}';

      await _api.post('/student/book', {
        'instructor_id': _selectedInstructorId,
        'date': dateStr,
        'time': timeStr,
        'duration': _duration,
        'pickup_address': _pickupCtrl.text.trim(),
      });

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Lesson booked!'),
          backgroundColor: Colors.green,
        ),
      );
      Navigator.pop(context);
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message), backgroundColor: Colors.red),
      );
    } finally {
      if (mounted) setState(() => _booking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Book a Lesson')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Instructor selector
                  Text(
                    'Select Instructor',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  ..._instructors.map((inst) {
                    final id = inst['id'];
                    final selected = _selectedInstructorId == id;
                    final profile = inst['profile'];
                    final rate = profile != null
                        ? profile['hourly_rate']
                        : null;
                    final rating = inst['avg_rating'];

                    return Card(
                      color: selected
                          ? Theme.of(context).colorScheme.primaryContainer
                          : null,
                      child: ListTile(
                        leading: CircleAvatar(
                          child: Text(inst['username'][0].toUpperCase()),
                        ),
                        title: Text(inst['username']),
                        subtitle: Text(
                          [
                            if (rate != null) '£$rate/hr',
                            if (rating != null) '⭐ $rating',
                            if (inst['review_count'] != null)
                              '${inst['review_count']} reviews',
                          ].join(' · '),
                        ),
                        trailing: selected
                            ? const Icon(
                                Icons.check_circle,
                                color: Colors.green,
                              )
                            : null,
                        onTap: () => setState(() => _selectedInstructorId = id),
                      ),
                    );
                  }),

                  const SizedBox(height: 24),

                  // Date & Time
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: _pickDate,
                          icon: const Icon(Icons.calendar_today),
                          label: Text(
                            _selectedDate != null
                                ? DateFormat(
                                    'EEE, MMM d',
                                  ).format(_selectedDate!)
                                : 'Select Date',
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: _pickTime,
                          icon: const Icon(Icons.access_time),
                          label: Text(
                            _selectedTime != null
                                ? _selectedTime!.format(context)
                                : 'Select Time',
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Duration
                  Text(
                    'Duration',
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  const SizedBox(height: 8),
                  SegmentedButton<int>(
                    segments: const [
                      ButtonSegment(value: 60, label: Text('1 hr')),
                      ButtonSegment(value: 90, label: Text('1.5 hr')),
                      ButtonSegment(value: 120, label: Text('2 hr')),
                    ],
                    selected: {_duration},
                    onSelectionChanged: (s) =>
                        setState(() => _duration = s.first),
                  ),
                  const SizedBox(height: 16),

                  // Pickup address
                  TextFormField(
                    controller: _pickupCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Pickup Address (optional)',
                      prefixIcon: Icon(Icons.location_on_outlined),
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Book button
                  _booking
                      ? const Center(child: CircularProgressIndicator())
                      : ElevatedButton.icon(
                          onPressed: _book,
                          icon: const Icon(Icons.check),
                          label: const Text('Confirm Booking'),
                        ),
                ],
              ),
            ),
    );
  }
}
