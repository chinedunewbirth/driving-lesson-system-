import 'package:flutter/material.dart';
import '../services/api_service.dart';

/// Manages authentication state across the app.
class AuthProvider extends ChangeNotifier {
  final _api = ApiService();

  Map<String, dynamic>? _user;
  bool _loading = true;

  Map<String, dynamic>? get user => _user;
  bool get isLoggedIn => _user != null;
  bool get isLoading => _loading;
  String get role => _user?['role'] ?? '';

  /// Try to restore session from stored token.
  Future<void> tryAutoLogin() async {
    final token = await _api.token;
    if (token == null) {
      _loading = false;
      notifyListeners();
      return;
    }
    try {
      final res = await _api.get('/auth/me');
      _user = res['user'];
    } catch (_) {
      await _api.clearToken();
    }
    _loading = false;
    notifyListeners();
  }

  Future<void> login(String username, String password) async {
    final res = await _api.post('/auth/login', {
      'username': username,
      'password': password,
    });
    await _api.saveToken(res['token']);
    _user = res['user'];
    notifyListeners();
  }

  Future<void> register(
    String username,
    String email,
    String password,
    String role,
  ) async {
    await _api.post('/auth/register', {
      'username': username,
      'email': email,
      'password': password,
      'role': role,
    });
  }

  Future<void> logout() async {
    await _api.clearToken();
    _user = null;
    notifyListeners();
  }
}
