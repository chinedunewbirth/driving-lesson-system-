import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class InstructorProfileScreen extends StatefulWidget {
  const InstructorProfileScreen({super.key});

  @override
  State<InstructorProfileScreen> createState() =>
      _InstructorProfileScreenState();
}

class _InstructorProfileScreenState extends State<InstructorProfileScreen> {
  final _api = ApiService();
  final _formKey = GlobalKey<FormState>();
  final _bioCtrl = TextEditingController();
  final _rateCtrl = TextEditingController();
  final _addressCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _radiusCtrl = TextEditingController();
  bool _loading = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await _api.get('/instructor/profile');
      final profile = res['user']?['profile'];
      if (profile != null) {
        _bioCtrl.text = profile['bio'] ?? '';
        _rateCtrl.text = '${profile['hourly_rate'] ?? ''}';
        _addressCtrl.text = profile['address'] ?? '';
        _phoneCtrl.text = profile['phone'] ?? '';
        _radiusCtrl.text = '${profile['service_radius_km'] ?? ''}';
      }
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await _api.put('/instructor/profile', {
        'bio': _bioCtrl.text.trim(),
        'hourly_rate': double.tryParse(_rateCtrl.text) ?? 35,
        'address': _addressCtrl.text.trim(),
        'phone': _phoneCtrl.text.trim(),
        'service_radius_km': double.tryParse(_radiusCtrl.text) ?? 10,
      });
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Profile updated'),
          backgroundColor: Colors.green,
        ),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message), backgroundColor: Colors.red),
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Profile')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Form(
                key: _formKey,
                child: Column(
                  children: [
                    TextFormField(
                      controller: _bioCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Bio',
                        prefixIcon: Icon(Icons.info_outline),
                      ),
                      maxLines: 3,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _rateCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Hourly Rate (£)',
                        prefixIcon: Icon(Icons.attach_money),
                      ),
                      keyboardType: TextInputType.number,
                      validator: (v) {
                        if (v == null || v.isEmpty) return 'Required';
                        if (double.tryParse(v) == null) return 'Invalid number';
                        return null;
                      },
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _addressCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Address',
                        prefixIcon: Icon(Icons.location_on_outlined),
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _phoneCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Phone',
                        prefixIcon: Icon(Icons.phone_outlined),
                      ),
                      keyboardType: TextInputType.phone,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _radiusCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Service Radius (km)',
                        prefixIcon: Icon(Icons.radar),
                      ),
                      keyboardType: TextInputType.number,
                    ),
                    const SizedBox(height: 24),
                    _saving
                        ? const CircularProgressIndicator()
                        : ElevatedButton.icon(
                            onPressed: _save,
                            icon: const Icon(Icons.save),
                            label: const Text('Save Profile'),
                          ),
                  ],
                ),
              ),
            ),
    );
  }
}
