//! Tim-Tim desktop commands. These only run after the UI has shown the user a confirmation (or the user chose
//! "Always allow" for a low/medium-risk skill). Inputs are validated again here as a second line of defence.
use std::fs;
use std::io::Read;
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

const MAX_OUT: usize = 4000;
const MAX_READ: u64 = 65_536;
const SHELL_TIMEOUT: Duration = Duration::from_secs(30);

#[cfg(target_os = "windows")]
fn base_cmd(program: &str) -> Command {
    use std::os::windows::process::CommandExt;
    let mut c = Command::new(program);
    c.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: no console flash
    c
}
#[cfg(not(target_os = "windows"))]
fn base_cmd(program: &str) -> Command {
    Command::new(program)
}

fn clean_name(s: &str) -> Result<String, String> {
    let t = s.trim();
    if t.is_empty() || t.chars().count() > 100 {
        return Err("invalid application name".into());
    }
    if t.chars().any(|c| matches!(c, '&' | '|' | '<' | '>' | '^' | '%' | '"' | '`' | '$' | ';' | '\n' | '\r' | '\0')) {
        return Err("the name contains forbidden characters".into());
    }
    Ok(t.to_string())
}

fn trim_out(mut s: String) -> String {
    if s.chars().count() > MAX_OUT {
        s = s.chars().take(MAX_OUT).collect::<String>() + "\n…(truncated)";
    }
    s
}

#[tauri::command]
fn open_app(name: String) -> Result<String, String> {
    let n = clean_name(&name)?;
    let name = n.as_str();
    #[cfg(target_os = "windows")]
    let launched: std::io::Result<bool> = base_cmd("cmd").args(["/C", "start", "", name]).status().map(|s| s.success());
    #[cfg(target_os = "macos")]
    let launched: std::io::Result<bool> = base_cmd("open").args(["-a", name]).status().map(|s| s.success());
    #[cfg(all(unix, not(target_os = "macos")))]
    let launched: std::io::Result<bool> = base_cmd(name).spawn().map(|_| true);
    match launched {
        Ok(true) => Ok(format!("Opened {n}.")),
        Ok(false) => Err(format!("Could not find an app called \"{n}\".")),
        Err(e) => Err(format!("Could not open {n}: {e}")),
    }
}

#[tauri::command]
fn close_app(name: String) -> Result<String, String> {
    let n = clean_name(&name)?;
    #[cfg(target_os = "windows")]
    let out = {
        let exe = if n.to_lowercase().ends_with(".exe") { n.clone() } else { format!("{n}.exe") };
        base_cmd("taskkill").args(["/IM", exe.as_str()]).output() // no /F: asks the app to close, so unsaved work can prompt
    };
    #[cfg(target_os = "macos")]
    let script = format!("tell application \"{n}\" to quit");
    #[cfg(target_os = "macos")]
    let out = base_cmd("osascript").args(["-e", script.as_str()]).output();
    #[cfg(all(unix, not(target_os = "macos")))]
    let out = base_cmd("pkill").args(["-x", n.as_str()]).output();
    match out {
        Ok(o) if o.status.success() => Ok(format!("Asked {n} to close.")),
        Ok(_) => Err(format!("{n} doesn't seem to be running.")),
        Err(e) => Err(format!("Could not close {n}: {e}")),
    }
}

#[tauri::command]
fn open_url(url: String) -> Result<String, String> {
    let u = url.trim();
    if !(u.starts_with("http://") || u.starts_with("https://")) || u.chars().any(|c| c.is_whitespace()) || u.len() > 2000 {
        return Err("only http(s) links are allowed".into());
    }
    #[cfg(target_os = "windows")]
    let r = base_cmd("rundll32").args(["url.dll,FileProtocolHandler", u]).status();
    #[cfg(target_os = "macos")]
    let r = base_cmd("open").arg(u).status();
    #[cfg(all(unix, not(target_os = "macos")))]
    let r = base_cmd("xdg-open").arg(u).status();
    r.map(|_| "Opened the page in your browser.".to_string()).map_err(|e| e.to_string())
}

#[tauri::command]
fn run_shell(command: String) -> Result<String, String> {
    if command.trim().is_empty() || command.chars().count() > 1000 {
        return Err("invalid command".into());
    }
    #[cfg(target_os = "windows")]
    let mut cmd = { let mut c = base_cmd("cmd"); c.args(["/C", command.as_str()]); c };
    #[cfg(not(target_os = "windows"))]
    let mut cmd = { let mut c = base_cmd("sh"); c.args(["-c", command.as_str()]); c };
    let mut child = cmd.stdout(Stdio::piped()).stderr(Stdio::piped()).spawn().map_err(|e| e.to_string())?;
    let mut so = child.stdout.take().ok_or("no stdout")?;
    let mut se = child.stderr.take().ok_or("no stderr")?;
    let h1 = thread::spawn(move || { let mut b = Vec::new(); let _ = so.by_ref().take(1_000_000).read_to_end(&mut b); b });
    let h2 = thread::spawn(move || { let mut b = Vec::new(); let _ = se.by_ref().take(1_000_000).read_to_end(&mut b); b });
    let start = Instant::now();
    let status = loop {
        match child.try_wait().map_err(|e| e.to_string())? {
            Some(s) => break s,
            None if start.elapsed() > SHELL_TIMEOUT => { let _ = child.kill(); let _ = child.wait(); return Err("The command took longer than 30 seconds and was stopped.".into()); }
            None => thread::sleep(Duration::from_millis(80)),
        }
    };
    let out = String::from_utf8_lossy(&h1.join().unwrap_or_default()).to_string();
    let err = String::from_utf8_lossy(&h2.join().unwrap_or_default()).to_string();
    let text = trim_out(format!("{}{}", out, if err.trim().is_empty() { String::new() } else { format!("\n[errors]\n{err}") }));
    if status.success() { Ok(if text.trim().is_empty() { "Done (no output).".into() } else { text }) } else { Err(format!("Exit code {:?}.\n{}", status.code(), text)) }
}

#[tauri::command]
fn read_file(path: String) -> Result<String, String> {
    if path.trim().is_empty() { return Err("empty path".into()); }
    let f = fs::File::open(&path).map_err(|e| format!("Cannot open the file: {e}"))?;
    let mut buf = Vec::new();
    f.take(MAX_READ).read_to_end(&mut buf).map_err(|e| e.to_string())?;
    Ok(String::from_utf8_lossy(&buf).to_string())
}

#[tauri::command]
fn write_file(path: String, content: String) -> Result<String, String> {
    if path.trim().is_empty() || content.len() > 100_000 { return Err("invalid path or content".into()); }
    fs::write(&path, content.as_bytes()).map_err(|e| format!("Cannot write the file: {e}"))?;
    Ok(format!("Wrote {} bytes to {}.", content.len(), path))
}

/// Undo for write_file: put the old text back, or remove the file if it did not exist before.
#[tauri::command]
fn restore_file(path: String, backup: Option<String>) -> Result<String, String> {
    match backup {
        Some(old) => fs::write(&path, old.as_bytes()).map(|_| "Restored the previous contents.".to_string()).map_err(|e| e.to_string()),
        None => match fs::remove_file(&path) { Ok(_) => Ok("Removed the file that was created.".into()), Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok("Nothing to remove.".into()), Err(e) => Err(e.to_string()) },
    }
}


// ───────── keyboard and mouse (Windows, through PowerShell; other systems are not supported yet) ─────────
fn b64(bytes: &[u8]) -> String {
    const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::new();
    for chunk in bytes.chunks(3) {
        let b0 = chunk[0] as u32;
        let b1 = *chunk.get(1).unwrap_or(&0) as u32;
        let b2 = *chunk.get(2).unwrap_or(&0) as u32;
        let n = (b0 << 16) | (b1 << 8) | b2;
        out.push(T[((n >> 18) & 63) as usize] as char);
        out.push(T[((n >> 12) & 63) as usize] as char);
        out.push(if chunk.len() > 1 { T[((n >> 6) & 63) as usize] as char } else { '=' });
        out.push(if chunk.len() > 2 { T[(n & 63) as usize] as char } else { '=' });
    }
    out
}

#[cfg(target_os = "windows")]
fn run_ps(script: &str) -> Result<String, String> {
    // -EncodedCommand (UTF-16LE base64) means no quoting problems whatever the text contains.
    let utf16: Vec<u8> = script.encode_utf16().flat_map(|u| u.to_le_bytes()).collect();
    let enc = b64(&utf16);
    let out = base_cmd("powershell")
        .args(["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc.as_str()])
        .output()
        .map_err(|e| format!("Could not start PowerShell: {e}"))?;
    if out.status.success() { Ok(String::from_utf8_lossy(&out.stdout).trim().to_string()) }
    else { Err(trim_out(String::from_utf8_lossy(&out.stderr).trim().to_string())) }
}
#[cfg(not(target_os = "windows"))]
fn run_ps(_script: &str) -> Result<String, String> {
    Err("Typing, key presses and clicks are only supported on Windows for now.".into())
}

fn sendkeys_escape(text: &str) -> String {
    let mut s = String::new();
    for c in text.chars() {
        match c {
            '+' | '^' | '%' | '~' | '(' | ')' | '{' | '}' | '[' | ']' => { s.push('{'); s.push(c); s.push('}'); }
            '\n' => s.push_str("{ENTER}"),
            '\t' => s.push_str("{TAB}"),
            '\r' => {}
            _ => s.push(c),
        }
    }
    s
}

fn send_keys(keys: &str) -> Result<String, String> {
    let q = keys.replace('\'', "''");
    run_ps(&format!(
        "Add-Type -AssemblyName System.Windows.Forms\nStart-Sleep -Milliseconds 300\n[System.Windows.Forms.SendKeys]::SendWait('{q}')"
    ))
}

#[tauri::command]
fn type_text(text: String) -> Result<String, String> {
    if text.is_empty() || text.chars().count() > 2000 { return Err("invalid text".into()); }
    send_keys(&sendkeys_escape(&text))?;
    Ok(format!("Typed {} characters.", text.chars().count()))
}

#[tauri::command]
fn press_key(key: String) -> Result<String, String> {
    let k = key.trim().to_lowercase();
    let code = match k.as_str() {
        "enter" => "{ENTER}", "tab" => "{TAB}", "esc" => "{ESC}", "up" => "{UP}", "down" => "{DOWN}", "left" => "{LEFT}", "right" => "{RIGHT}",
        "backspace" => "{BACKSPACE}", "delete" => "{DELETE}", "space" => " ", "home" => "{HOME}", "end" => "{END}", "pageup" => "{PGUP}", "pagedown" => "{PGDN}",
        "ctrl+a" => "^a", "ctrl+c" => "^c", "ctrl+v" => "^v", "ctrl+x" => "^x", "ctrl+z" => "^z", "ctrl+s" => "^s", "ctrl+f" => "^f",
        "alt+left" => "%{LEFT}", "alt+right" => "%{RIGHT}", "alt+f4" => "%{F4}",
        _ => return Err("that key is not allowed".into()),
    };
    send_keys(code)?;
    Ok(format!("Pressed {k}."))
}

#[tauri::command]
fn click(x: i32, y: i32) -> Result<String, String> {
    if !(0..=20000).contains(&x) || !(0..=20000).contains(&y) { return Err("coordinates out of range".into()); }
    run_ps(&format!(
        "Add-Type @\"\nusing System.Runtime.InteropServices;\npublic class TimMouse {{\n  [DllImport(\"user32.dll\")] public static extern bool SetProcessDPIAware();\n  [DllImport(\"user32.dll\")] public static extern bool SetCursorPos(int x, int y);\n  [DllImport(\"user32.dll\")] public static extern void mouse_event(int f, int dx, int dy, int d, int e);\n}}\n\"@\n[TimMouse]::SetProcessDPIAware() | Out-Null\nStart-Sleep -Milliseconds 300\n[TimMouse]::SetCursorPos({x}, {y}) | Out-Null\n[TimMouse]::mouse_event(2,0,0,0,0)\n[TimMouse]::mouse_event(4,0,0,0,0)"
    ))?;
    Ok(format!("Clicked at {x}, {y}."))
}

// ───────── files, clipboard, media and system helpers ─────────
fn ps_quote(s: &str) -> String { s.replace('\'', "''") }

#[tauri::command]
fn list_dir(path: String) -> Result<String, String> {
    if path.trim().is_empty() { return Err("empty path".into()); }
    let rd = fs::read_dir(&path).map_err(|e| format!("Cannot open the folder: {e}"))?;
    let mut dirs: Vec<String> = Vec::new();
    let mut files: Vec<(String, u64)> = Vec::new();
    for entry in rd.flatten() {
        let name = entry.file_name().to_string_lossy().to_string();
        match entry.metadata() {
            Ok(m) if m.is_dir() => dirs.push(name),
            Ok(m) => files.push((name, m.len())),
            Err(_) => files.push((name, 0)),
        }
    }
    dirs.sort_by_key(|n| n.to_lowercase());
    files.sort_by_key(|(n, _)| n.to_lowercase());
    let total = dirs.len() + files.len();
    let mut lines: Vec<String> = dirs.iter().map(|d| format!("[folder] {d}")).collect();
    lines.extend(files.iter().map(|(n, sz)| format!("{n} ({} KB)", (sz + 1023) / 1024)));
    let more = total.saturating_sub(200);
    lines.truncate(200);
    let mut out = lines.join("\n");
    if more > 0 { out.push_str(&format!("\n…and {more} more")); }
    Ok(if out.is_empty() { "The folder is empty.".into() } else { trim_out(out) })
}

#[tauri::command]
fn create_folder(path: String) -> Result<String, String> {
    if path.trim().is_empty() { return Err("empty path".into()); }
    fs::create_dir_all(&path).map_err(|e| format!("Cannot create the folder: {e}"))?;
    Ok(format!("Created {path}."))
}

#[tauri::command]
fn open_path(path: String) -> Result<String, String> {
    if path.trim().is_empty() || !std::path::Path::new(&path).exists() { return Err("That file or folder does not exist.".into()); }
    #[cfg(target_os = "windows")]
    let r = base_cmd("rundll32").args(["url.dll,FileProtocolHandler", path.as_str()]).status();
    #[cfg(target_os = "macos")]
    let r = base_cmd("open").arg(path.as_str()).status();
    #[cfg(all(unix, not(target_os = "macos")))]
    let r = base_cmd("xdg-open").arg(path.as_str()).status();
    r.map(|_| format!("Opened {path}.")).map_err(|e| e.to_string())
}

#[tauri::command]
fn copy_file(from: String, to: String) -> Result<String, String> {
    if from.trim().is_empty() || to.trim().is_empty() { return Err("empty path".into()); }
    if std::path::Path::new(&to).exists() { return Err("The destination already exists, so nothing was copied.".into()); }
    fs::copy(&from, &to).map(|_| format!("Copied to {to}.")).map_err(|e| format!("Cannot copy: {e}"))
}

#[tauri::command]
fn move_file(from: String, to: String) -> Result<String, String> {
    if from.trim().is_empty() || to.trim().is_empty() { return Err("empty path".into()); }
    if std::path::Path::new(&to).exists() { return Err("The destination already exists, so nothing was moved.".into()); }
    match fs::rename(&from, &to) {
        Ok(_) => Ok(format!("Moved to {to}.")),
        Err(_) => {
            // across drives rename fails: copy then remove (files only)
            if std::path::Path::new(&from).is_file() {
                fs::copy(&from, &to).map_err(|e| format!("Cannot move: {e}"))?;
                fs::remove_file(&from).map_err(|e| format!("Copied, but could not remove the original: {e}"))?;
                Ok(format!("Moved to {to}."))
            } else { Err("Folders can't be moved across drives yet.".into()) }
        }
    }
}

#[tauri::command]
fn delete_file(path: String) -> Result<String, String> {
    if path.trim().is_empty() { return Err("empty path".into()); }
    let p = ps_quote(&path);
    run_ps(&format!(
        "Add-Type -AssemblyName Microsoft.VisualBasic\n$p = '{p}'\nif (-not (Test-Path -LiteralPath $p)) {{ throw 'Not found' }}\nif (Test-Path -LiteralPath $p -PathType Container) {{ [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($p, 'OnlyErrorDialogs', 'SendToRecycleBin') }} else {{ [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p, 'OnlyErrorDialogs', 'SendToRecycleBin') }}"
    ))?;
    Ok(format!("Moved {path} to the Recycle Bin (you can restore it from there)."))
}

#[tauri::command]
fn clipboard_read() -> Result<String, String> {
    let t = run_ps("Get-Clipboard -Raw")?;
    Ok(if t.trim().is_empty() { "The clipboard has no text.".into() } else { trim_out(t) })
}

#[tauri::command]
fn clipboard_write(text: String) -> Result<String, String> {
    if text.is_empty() || text.chars().count() > 5000 { return Err("invalid text".into()); }
    run_ps(&format!("Set-Clipboard -Value '{}'", ps_quote(&text)))?;
    Ok("Copied to the clipboard. You can paste it now.".into())
}

#[tauri::command]
fn media_key(key: String, times: Option<u32>) -> Result<String, String> {
    let code = match key.trim().to_lowercase().as_str() {
        "volume_up" => 175, "volume_down" => 174, "mute" => 173, "play_pause" => 179, "next_track" => 176, "prev_track" => 177,
        _ => return Err("that media key is not allowed".into()),
    };
    let n = times.unwrap_or(1).clamp(1, 25);
    run_ps(&format!("$w = New-Object -ComObject WScript.Shell\n1..{n} | ForEach-Object {{ $w.SendKeys([char]{code}) }}"))?;
    Ok(format!("Pressed {} x{n}.", key.trim()))
}

#[tauri::command]
fn system_info() -> Result<String, String> {
    run_ps(r#"$os = Get-CimInstance Win32_OperatingSystem
$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
$b = Get-CimInstance Win32_Battery
$t = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$f = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$bat = if ($b) { "$($b.EstimatedChargeRemaining)%" } else { "no battery" }
"OS: $($os.Caption)`nCPU load: $cpu%`nMemory: $([math]::Round($t - $f, 1)) of $t GB used`nBattery: $bat""#)
}

#[tauri::command]
fn lock_screen() -> Result<String, String> {
    #[cfg(target_os = "windows")]
    {
        base_cmd("rundll32").args(["user32.dll,LockWorkStation"]).status().map_err(|e| e.to_string())?;
        Ok("Locked the computer.".into())
    }
    #[cfg(not(target_os = "windows"))]
    { Err("Locking the screen is only supported on Windows for now.".into()) }
}

// ───────── WhatsApp (official links only: nothing is read from WhatsApp, nothing unofficial is used) ─────────
fn url_encode(s: &str) -> String {
    let mut out = String::new();
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => out.push(b as char),
            _ => out.push_str(&format!("%{:02X}", b)),
        }
    }
    out
}

fn clean_phone(p: &str) -> Result<String, String> {
    let d: String = p.chars().filter(|c| c.is_ascii_digit()).collect();
    if d.len() < 8 || d.len() > 15 { return Err("That phone number doesn't look right. Use the full number with the country code.".into()); }
    Ok(d)
}

fn open_link(link: &str) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    let r = base_cmd("rundll32").args(["url.dll,FileProtocolHandler", link]).status();
    #[cfg(target_os = "macos")]
    let r = base_cmd("open").arg(link).status();
    #[cfg(all(unix, not(target_os = "macos")))]
    let r = base_cmd("xdg-open").arg(link).status();
    r.map(|_| ()).map_err(|e| format!("Could not open WhatsApp: {e}"))
}

#[tauri::command]
fn whatsapp_open(phone: Option<String>) -> Result<String, String> {
    let link = match phone.as_deref().map(str::trim).filter(|p| !p.is_empty()) {
        Some(p) => format!("whatsapp://send?phone={}", clean_phone(p)?),
        None => "whatsapp://".to_string(),
    };
    open_link(&link)?;
    Ok("Opened WhatsApp.".into())
}

#[tauri::command]
fn whatsapp_send(phone: String, text: String, auto_send: bool) -> Result<String, String> {
    let p = clean_phone(&phone)?;
    if text.trim().is_empty() || text.chars().count() > 1000 { return Err("invalid message".into()); }
    open_link(&format!("whatsapp://send?phone={}&text={}", p, url_encode(&text)))?;
    #[cfg(target_os = "windows")]
    {
        if auto_send {
            std::thread::sleep(Duration::from_millis(3500));      // let WhatsApp open the chat with the message typed in
            send_keys("{ENTER}")?;
            return Ok("Message sent.".into());
        }
    }
    let _ = auto_send;
    Ok("WhatsApp is open with your message ready. Press Send.".into())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![open_app, close_app, open_url, run_shell, read_file, write_file, restore_file, type_text, press_key, click, list_dir, create_folder, open_path, copy_file, move_file, delete_file, clipboard_read, clipboard_write, media_key, system_info, lock_screen, whatsapp_open, whatsapp_send])
        .run(tauri::generate_context!())
        .expect("error while running Tim-Tim");
}
