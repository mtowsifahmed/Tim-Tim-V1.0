// Tim-Tim phone app: a thin, fast wrapper around the hosted Tim-Tim web app.
// Everything (chat, voice, memory, world monitor, settings) comes from the website, so the phone app always matches it.
// This file adds what a browser tab cannot: a real app icon, microphone permission, hands-free audio playback and the Back button.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';

/// Where the web app lives. Override at build time: flutter build apk --dart-define=APP_URL=https://your-address
const String kAppUrl = String.fromEnvironment('APP_URL', defaultValue: 'https://tim-tim-v1-app.onrender.com');
const Color kBackground = Color(0xFF03050A);

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: kBackground,
    systemNavigationBarColor: kBackground,
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarIconBrightness: Brightness.light,
  ));
  runApp(const TimTimApp());
}

class TimTimApp extends StatelessWidget {
  const TimTimApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Tim-Tim',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(useMaterial3: true).copyWith(scaffoldBackgroundColor: kBackground),
      home: const Shell(),
    );
  }
}

class Shell extends StatefulWidget {
  const Shell({super.key});

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  late final WebViewController _controller;
  bool _loading = true;
  bool _offline = false;

  @override
  void initState() {
    super.initState();
    final String appHost = Uri.parse(kAppUrl).host;

    _controller = WebViewController(
      // The web app asks for the microphone when you hold the mic button: ask Android first, then let the page use it.
      onPermissionRequest: (WebViewPermissionRequest request) async {
        final PermissionStatus mic = await Permission.microphone.request();
        if (mic.isGranted) {
          await request.grant();
        } else {
          await request.deny();
        }
      },
    )
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(kBackground)
      // window.open() (used by the source chips under answers) is routed here and opened in the phone's browser.
      ..addJavaScriptChannel('TimTimBridge', onMessageReceived: (JavaScriptMessage message) {
        final Uri? uri = Uri.tryParse(message.message);
        if (uri != null && (uri.scheme == 'https' || uri.scheme == 'http')) {
          launchUrl(uri, mode: LaunchMode.externalApplication);
        }
      })
      ..setNavigationDelegate(NavigationDelegate(
        onPageStarted: (String url) => setState(() {
          _loading = true;
          _offline = false;
        }),
        onPageFinished: (String url) {
          setState(() => _loading = false);
          _controller.runJavaScript(
              "window.open = function(u){ TimTimBridge.postMessage(String(u)); return null; };");
        },
        onWebResourceError: (WebResourceError error) {
          if (error.isForMainFrame ?? true) {
            setState(() {
              _offline = true;
              _loading = false;
            });
          }
        },
        onNavigationRequest: (NavigationRequest request) {
          final Uri? uri = Uri.tryParse(request.url);
          final bool web = uri != null && (uri.scheme == 'https' || uri.scheme == 'http');
          if (!web || uri.host == appHost) return NavigationDecision.navigate;
          launchUrl(uri, mode: LaunchMode.externalApplication); // other websites open in the browser, not inside Tim-Tim
          return NavigationDecision.prevent;
        },
      ));

    final platform = _controller.platform;
    if (platform is AndroidWebViewController) {
      // Lets Tim-Tim's voice reply play without an extra tap.
      platform.setMediaPlaybackRequiresUserGesture(false);
    }
    _load();
  }

  void _load() {
    setState(() {
      _offline = false;
      _loading = true;
    });
    _controller.loadRequest(Uri.parse(kAppUrl));
  }

  @override
  Widget build(BuildContext context) {
    return WillPopScope(
      // Back goes to the previous page inside the app; on the first page it closes the app as usual.
      onWillPop: () async {
        if (await _controller.canGoBack()) {
          await _controller.goBack();
          return false;
        }
        return true;
      },
      child: Scaffold(
        backgroundColor: kBackground,
        body: SafeArea(
          child: Stack(
            children: <Widget>[
              WebViewWidget(controller: _controller),
              if (_loading && !_offline) const LinearProgressIndicator(minHeight: 2, backgroundColor: Colors.transparent),
              if (_offline) _OfflineView(onRetry: _load),
            ],
          ),
        ),
      ),
    );
  }
}

class _OfflineView extends StatelessWidget {
  const _OfflineView({required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: kBackground,
      alignment: Alignment.center,
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Image.asset('assets/icon.png', width: 96, height: 96),
          const SizedBox(height: 24),
          const Text("Can't reach Tim-Tim", style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          const Text(
            'Check your internet connection and try again. If it keeps failing, the server may be waking up: wait a minute.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.white60),
          ),
          const SizedBox(height: 24),
          FilledButton(onPressed: onRetry, child: const Text('Try again')),
        ],
      ),
    );
  }
}
