use std::collections::HashMap;
use std::env;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

const INDEX_HTML: &str = include_str!("../ui/index.html");
const STYLES_CSS: &str = include_str!("../ui/styles.css");
const APP_JS: &str = include_str!("../ui/app.js");
const EDITOR_JS: &str = include_str!("../ui/editor.js");
const MAP_JS: &str = include_str!("../ui/map.js");

const PIN_GATE_HTML: &str = r#"<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1.0" />
<title>CMDAI CODE · Unlock</title>
<style>
  body { margin:0; height:100dvh; display:flex; align-items:center; justify-content:center; background:#f4f5f7; font-family:-apple-system,BlinkMacSystemFont,"Inter","Segoe UI",sans-serif; color:#111827; }
  .card { width:100%; max-width:340px; background:#fff; border:1px solid #e4e7ec; border-radius:14px; padding:26px; box-shadow:0 12px 32px rgba(15,23,42,.1); text-align:center; }
  .logo { width:40px; height:40px; margin:0 auto 10px; border-radius:10px; background:#18181b; color:#fff; font-family:monospace; font-weight:800; display:flex; align-items:center; justify-content:center; }
  h2 { margin:0 0 6px; font-size:17px; }
  p { margin:0 0 16px; font-size:12.5px; color:#6b7280; }
  input { width:100%; box-sizing:border-box; text-align:center; font-family:monospace; font-size:24px; letter-spacing:.35em; padding:10px; border-radius:9px; border:1px solid #cfd5e1; margin-bottom:10px; outline:none; }
  input:focus { border-color:#2563eb; }
  button { width:100%; background:#18181b; color:#fff; border:none; border-radius:9px; padding:10px; font-weight:600; cursor:pointer; }
  .err { margin-top:8px; color:#dc2626; font-size:12px; min-height:16px; }
</style>
</head>
<body>
  <div class="card">
    <div class="logo">CC</div>
    <h2>CMDAI CODE</h2>
    <p>Enter the 6-digit pairing PIN from your PC tunnel terminal.</p>
    <form id="f">
      <input id="pin" type="text" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="000000" required autofocus />
      <button type="submit">Unlock Workspace</button>
    </form>
    <div id="err" class="err"></div>
  </div>
  <script>
    document.getElementById("f").addEventListener("submit", async (e) => {
      e.preventDefault();
      const pin = document.getElementById("pin").value.trim();
      const err = document.getElementById("err");
      err.textContent = "";
      const r = await fetch("/api/web/verify-pin", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({pin}) });
      if (r.ok) { location.reload(); } else { err.textContent = "Incorrect PIN."; }
    });
  </script>
</body>
</html>"#;

struct Config {
    host: String,
    port: u16,
    backend: String,
    token: String,
    pin: String,
}

fn parse_args() -> Config {
    let mut cfg = Config {
        host: "127.0.0.1".to_string(),
        port: 8787,
        backend: "127.0.0.1:7860".to_string(),
        token: String::new(),
        pin: String::new(),
    };
    let args: Vec<String> = env::args().collect();
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--host" if i + 1 < args.len() => { cfg.host = args[i + 1].clone(); i += 2; }
            "--port" if i + 1 < args.len() => { if let Ok(p) = args[i + 1].parse::<u16>() { cfg.port = p; } i += 2; }
            "--backend" if i + 1 < args.len() => { cfg.backend = args[i + 1].clone(); i += 2; }
            "--token" if i + 1 < args.len() => { cfg.token = args[i + 1].clone(); i += 2; }
            "--pin" if i + 1 < args.len() => { cfg.pin = args[i + 1].clone(); i += 2; }
            _ => i += 1,
        }
    }
    cfg
}

fn send_response(
    stream: &mut TcpStream,
    status: &str,
    content_type: &str,
    extra_headers: &[(&str, &str)],
    body: &[u8],
) {
    let mut head = format!(
        "HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nX-Robots-Tag: noindex, nofollow\r\nCache-Control: no-store\r\nConnection: close\r\n",
        status,
        content_type,
        body.len()
    );
    for (k, v) in extra_headers {
        head.push_str(&format!("{}: {}\r\n", k, v));
    }
    head.push_str("\r\n");
    let _ = stream.write_all(head.as_bytes());
    let _ = stream.write_all(body);
    let _ = stream.flush();
}

fn parse_cookies(headers: &HashMap<String, String>) -> HashMap<String, String> {
    let mut out = HashMap::new();
    if let Some(raw) = headers.get("cookie") {
        for part in raw.split(';') {
            if let Some((k, v)) = part.trim().split_once('=') {
                out.insert(k.trim().to_string(), v.trim().to_string());
            }
        }
    }
    out
}

fn extract_json_field(body: &str, field: &str) -> String {
    let needle = format!("\"{}\"", field);
    if let Some(pos) = body.find(&needle) {
        let rest = &body[pos + needle.len()..];
        if let Some(colon) = rest.find(':') {
            let val = rest[colon + 1..].trim();
            if let Some(stripped) = val.strip_prefix('"') {
                if let Some(end) = stripped.find('"') {
                    return stripped[..end].to_string();
                }
            }
        }
    }
    String::new()
}

fn proxy_to_backend_streaming(
    client: &mut TcpStream,
    cfg: &Config,
    method: &str,
    path: &str,
    headers: &HashMap<String, String>,
    body: &[u8],
) {
    let mut backend = match TcpStream::connect(&cfg.backend) {
        Ok(s) => s,
        Err(_) => {
            let err = br#"{"error":"CMDAI CODE backend is offline"}"#;
            send_response(client, "502 Bad Gateway", "application/json", &[], err);
            return;
        }
    };
    // No artificial read timeout on SSE / agent streams so long multi-step tasks never drop with network error
    let _ = backend.set_read_timeout(None);
    let _ = backend.set_write_timeout(Some(Duration::from_secs(30)));

    let mut req = format!(
        "{} {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\nContent-Length: {}\r\n",
        method,
        path,
        cfg.backend,
        body.len()
    );
    if let Some(ct) = headers.get("content-type") {
        req.push_str(&format!("Content-Type: {}\r\n", ct));
    }
    if let Some(acc) = headers.get("accept") {
        req.push_str(&format!("Accept: {}\r\n", acc));
    }
    if !cfg.token.is_empty() {
        req.push_str(&format!("X-CMDAI-Token: {}\r\n", cfg.token));
    }
    req.push_str("\r\n");

    if backend.write_all(req.as_bytes()).is_err() || backend.write_all(body).is_err() {
        let err = br#"{"error":"Failed to forward request to backend"}"#;
        send_response(client, "502 Bad Gateway", "application/json", &[], err);
        return;
    }
    let _ = backend.flush();

    // Stream response chunks immediately so SSE (text/event-stream) works in real time
    let mut buf = [0u8; 8192];
    loop {
        match backend.read(&mut buf) {
            Ok(0) => break,
            Ok(n) => {
                if client.write_all(&buf[..n]).is_err() {
                    break;
                }
                let _ = client.flush();
            }
            Err(_) => break,
        }
    }
}

fn handle_client(mut stream: TcpStream, cfg: Arc<Config>) {
    let _ = stream.set_read_timeout(Some(Duration::from_secs(15)));
    let mut reader = match stream.try_clone() {
        Ok(cloned) => BufReader::new(cloned),
        Err(_) => return,
    };

    let mut request_line = String::new();
    if reader.read_line(&mut request_line).unwrap_or(0) == 0 {
        return;
    }
    let parts: Vec<&str> = request_line.trim().split_whitespace().collect();
    if parts.len() < 2 {
        return;
    }
    let method = parts[0];
    let full_path = parts[1];
    let clean_path = full_path.split('?').next().unwrap_or(full_path);

    let mut headers = HashMap::new();
    let mut content_len: usize = 0;
    loop {
        let mut line = String::new();
        if reader.read_line(&mut line).unwrap_or(0) == 0 {
            break;
        }
        let trimmed = line.trim();
        if trimmed.is_empty() {
            break;
        }
        if let Some((k, v)) = trimmed.split_once(':') {
            let key = k.trim().to_ascii_lowercase();
            let val = v.trim().to_string();
            if key == "content-length" {
                content_len = val.parse::<usize>().unwrap_or(0).min(12 * 1024 * 1024);
            }
            headers.insert(key, val);
        }
    }

    let mut body = vec![0u8; content_len];
    if content_len > 0 {
        let _ = reader.read_exact(&mut body);
    }

    let cookies = parse_cookies(&headers);
    let remote_mode = !cfg.token.is_empty();
    let pin_required = remote_mode && !cfg.pin.is_empty();

    // PIN verification endpoint
    if method == "POST" && clean_path == "/api/web/verify-pin" {
        let tok_ok = !remote_mode
            || cookies.get("cmdai_tok").map(|v| v == &cfg.token).unwrap_or(false);
        if !tok_ok {
            send_response(&mut stream, "401 Unauthorized", "application/json", &[], br#"{"ok":false}"#);
            return;
        }
        let body_str = String::from_utf8_lossy(&body);
        if extract_json_field(&body_str, "pin") == cfg.pin {
            let cookie = format!("cmdai_pin={}; Path=/; HttpOnly; SameSite=Lax", cfg.pin);
            send_response(&mut stream, "200 OK", "application/json", &[("Set-Cookie", &cookie)], br#"{"ok":true}"#);
        } else {
            send_response(&mut stream, "403 Forbidden", "application/json", &[], br#"{"ok":false}"#);
        }
        return;
    }

    // Remote entry route /r/<token>
    if remote_mode {
        let expected_route = format!("/r/{}", cfg.token);
        if method == "GET" && clean_path == expected_route {
            let cookie = format!("cmdai_tok={}; Path=/; HttpOnly; SameSite=Lax", cfg.token);
            let pin_ok = !pin_required || cookies.get("cmdai_pin").map(|v| v == &cfg.pin).unwrap_or(false);
            let html = if pin_ok { INDEX_HTML } else { PIN_GATE_HTML };
            send_response(&mut stream, "200 OK", "text/html; charset=utf-8", &[("Set-Cookie", &cookie)], html.as_bytes());
            return;
        }
    }

    // Static assets (always served)
    if method == "GET" {
        match clean_path {
            "/styles.css" => { send_response(&mut stream, "200 OK", "text/css; charset=utf-8", &[], STYLES_CSS.as_bytes()); return; }
            "/app.js" => { send_response(&mut stream, "200 OK", "application/javascript; charset=utf-8", &[], APP_JS.as_bytes()); return; }
            "/editor.js" => { send_response(&mut stream, "200 OK", "application/javascript; charset=utf-8", &[], EDITOR_JS.as_bytes()); return; }
            "/map.js" => { send_response(&mut stream, "200 OK", "application/javascript; charset=utf-8", &[], MAP_JS.as_bytes()); return; }
            _ => {}
        }
    }

    // Auth check for remote mode
    if remote_mode {
        let tok_ok = cookies.get("cmdai_tok").map(|v| v == &cfg.token).unwrap_or(false)
            || headers.get("x-cmdai-token").map(|v| v == &cfg.token).unwrap_or(false);
        if !tok_ok {
            send_response(&mut stream, "401 Unauthorized", "text/plain; charset=utf-8", &[], b"Unauthorized - scan the CMDAI CODE QR code to connect.");
            return;
        }
        if pin_required {
            let pin_ok = cookies.get("cmdai_pin").map(|v| v == &cfg.pin).unwrap_or(false);
            if !pin_ok {
                if clean_path == "/" {
                    send_response(&mut stream, "200 OK", "text/html; charset=utf-8", &[], PIN_GATE_HTML.as_bytes());
                } else {
                    send_response(&mut stream, "403 Forbidden", "application/json", &[], br#"{"error":"PIN required"}"#);
                }
                return;
            }
        }
    }

    // Root index.html (exact CMDAI CODE DESKTOP UI)
    if method == "GET" && clean_path == "/" {
        send_response(&mut stream, "200 OK", "text/html; charset=utf-8", &[], INDEX_HTML.as_bytes());
        return;
    }

    // Forward all /api/* calls (including SSE streaming) to FastAPI desktop_bridge
    if clean_path.starts_with("/api/") {
        proxy_to_backend_streaming(&mut stream, &cfg, method, full_path, &headers, &body);
        return;
    }

    send_response(&mut stream, "404 Not Found", "text/plain; charset=utf-8", &[], b"Not Found");
}

fn main() {
    let cfg = Arc::new(parse_args());
    let addr = format!("{}:{}", cfg.host, cfg.port);
    let listener = TcpListener::bind(&addr).unwrap_or_else(|e| {
        eprintln!("[cmdai-web] Failed to bind {}: {}", addr, e);
        std::process::exit(1);
    });
    println!("[cmdai-web] Listening on http://{} -> backend {}", addr, cfg.backend);

    for incoming in listener.incoming() {
        if let Ok(stream) = incoming {
            let cfg_ref = Arc::clone(&cfg);
            thread::spawn(move || handle_client(stream, cfg_ref));
        }
    }
}
