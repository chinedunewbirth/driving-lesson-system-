import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../constants.dart';

/// Centralized HTTP client that attaches the JWT token to every request.
class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  final _storage = const FlutterSecureStorage();
  static const _tokenKey = 'auth_token';

  // ── Token management ─────────────────────────────

  Future<String?> get token async => _storage.read(key: _tokenKey);
  Future<void> saveToken(String token) =>
      _storage.write(key: _tokenKey, value: token);
  Future<void> clearToken() => _storage.delete(key: _tokenKey);

  Future<Map<String, String>> _headers() async {
    final t = await token;
    return {
      'Content-Type': 'application/json',
      if (t != null) 'Authorization': 'Bearer $t',
    };
  }

  // ── Generic HTTP helpers ─────────────────────────

  Future<Map<String, dynamic>> get(String path) async {
    try {
      final res = await http
          .get(
            Uri.parse('${AppConstants.baseUrl}$path'),
            headers: await _headers(),
          )
          .timeout(const Duration(seconds: 15));
      return _handleResponse(res);
    } on SocketException {
      throw const ApiException(
        statusCode: 0,
        message:
            'Cannot connect to server. Check your network and server address.',
      );
    } on HttpException {
      throw const ApiException(
        statusCode: 0,
        message: 'Connection error. Please try again.',
      );
    }
  }

  Future<Map<String, dynamic>> post(
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    try {
      final res = await http
          .post(
            Uri.parse('${AppConstants.baseUrl}$path'),
            headers: await _headers(),
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(const Duration(seconds: 15));
      return _handleResponse(res);
    } on SocketException {
      throw const ApiException(
        statusCode: 0,
        message:
            'Cannot connect to server. Check your network and server address.',
      );
    } on HttpException {
      throw const ApiException(
        statusCode: 0,
        message: 'Connection error. Please try again.',
      );
    }
  }

  Future<Map<String, dynamic>> put(
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    try {
      final res = await http
          .put(
            Uri.parse('${AppConstants.baseUrl}$path'),
            headers: await _headers(),
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(const Duration(seconds: 15));
      return _handleResponse(res);
    } on SocketException {
      throw const ApiException(
        statusCode: 0,
        message:
            'Cannot connect to server. Check your network and server address.',
      );
    } on HttpException {
      throw const ApiException(
        statusCode: 0,
        message: 'Connection error. Please try again.',
      );
    }
  }

  Map<String, dynamic> _handleResponse(http.Response res) {
    Map<String, dynamic> data;
    try {
      data = jsonDecode(res.body) as Map<String, dynamic>;
    } catch (_) {
      throw ApiException(
        statusCode: res.statusCode,
        message: 'Server error (${res.statusCode}). Please try again later.',
      );
    }
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return data;
    }
    throw ApiException(
      statusCode: res.statusCode,
      message: data['error'] ?? 'Something went wrong',
    );
  }
}

class ApiException implements Exception {
  final int statusCode;
  final String message;
  const ApiException({required this.statusCode, required this.message});

  @override
  String toString() => message;
}
