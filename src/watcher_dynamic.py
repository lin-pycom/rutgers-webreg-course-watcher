#!/usr/bin/env python3
"""Dynamically watch active Schedru snipes and submit one opening."""

from __future__ import annotations

import json
import logging
import re
import queue
import subprocess
import sys
import threading
import time
from typing import Any


TERM_LABEL = "Spring 2027"
SCHEDRU_PREFIX = "https://www.schedru.me/dashboard"
WEBREG_PREFIX = "https://sims.rutgers.edu/webreg/"
POLL_SECONDS = 5
SCHEDRU_REFRESH_SECONDS = 5
WEBREG_KEEPALIVE_SECONDS = 60

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def safari_js(url_prefix: str, source: str) -> str:
    """Run JavaScript only in a matching tab that is already open in Safari."""
    encoded_source = json.dumps(source)
    encoded_prefix = json.dumps(url_prefix)
    script = f"""
const Safari = Application('Safari');
let target = null;
for (const win of Safari.windows()) {{
  for (const tab of win.tabs()) {{
    const u = tab.url();
    if (u && u.startsWith({encoded_prefix})) target = tab;
  }}
}}
if (!target) throw new Error('No already-open Safari tab found for ' + {encoded_prefix});
Safari.doJavaScript({encoded_source}, {{in: target}}).toString();
"""
    completed = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(message or "Safari automation failed.")
    return completed.stdout.strip()


def parse_page_json(raw: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        raise RuntimeError(f"Could not read the page state: {raw[:300]}")
    return json.loads(match.group(0))


def schedru_state() -> dict[str, Any]:
    source = f"""
(() => {{
  const rawBody = document.body?.innerText || '';
  const body = rawBody.replace(/\\s+/g, ' ').trim();
  const activeMarker = body.indexOf('ACTIVE SNIPES');
  const inactiveMarker = body.indexOf('INACTIVE SNIPES', activeMarker + 1);
  const activeText = activeMarker < 0 ? '' : body.slice(
    activeMarker,
    inactiveMarker < 0 ? body.length : inactiveMarker
  );
  const inactiveText = inactiveMarker < 0 ? '' : body.slice(inactiveMarker);

  function parseCards(sectionText) {{
    const cards = {{}};
    const matches = Array.from(sectionText.matchAll(/\\bINDEX\\s+(\\d{{5}})\\b/gi));
    for (let i = 0; i < matches.length; i++) {{
      const index = matches[i][1];
      const start = matches[i].index;
      const end = i + 1 < matches.length ? matches[i + 1].index : sectionText.length;
      const cardText = sectionText.slice(start, end);
      if (/\\bDEACTIVATED BY USER\\b/i.test(cardText)) cards[index] = 'inactive';
      else if (/\\[EMAILED\\]/i.test(cardText)) cards[index] = 'opened-notified';
      else if (/\\bCLOSED\\b/i.test(cardText)) cards[index] = 'closed';
      else if (/\\bOPEN\\b/i.test(cardText)) cards[index] = 'open';
      else cards[index] = 'unknown';
    }}
    return cards;
  }}

  const activeCards = parseCards(activeText);
  const inactiveCards = parseCards(inactiveText);
  const cards = {{...inactiveCards, ...activeCards}};

  function getCardText(index) {{
    const candidates = Array.from(document.querySelectorAll('body *'))
      .filter(el => new RegExp('\\\\bINDEX\\\\s+' + index + '\\\\b', 'i').test(el.innerText || ''))
      .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
    if (!candidates.length) return '';
    let card = candidates[0];
    while (card.parentElement) {{
      const parentText = card.parentElement.innerText || '';
      const indexes = parentText.match(/\\bINDEX\\s+\\d{{5}}\\b/gi) || [];
      if (indexes.length !== 1 || !indexes[0].includes(index)) break;
      card = card.parentElement;
    }}
    return card.innerText || '';
  }}

  function getCourseTitle(cardText) {{
    const lines = cardText.split(/\\r?\\n/).map(line => line.replace(/\\s+/g, ' ').trim()).filter(Boolean);
    const codeLine = lines.findIndex(line => /\\b\\d{{2,3}}:\\d{{3}}:\\d{{3}}\\b/.test(line));
    const candidates = codeLine >= 0 ? lines.slice(codeLine + 1) : lines;
    for (const line of candidates) {{
      if (/^\\d{{1,2}}$/.test(line)) continue;
      if (/^NB\\s+(SPRING|FALL|WINTER|SUMMER)\\s+\\d{{4}}$/i.test(line)) continue;
      if (/^(INDEX|EMAILS|TEXTS)\\b/i.test(line)) continue;
      if (/\\b(CLOSED|OPEN|AS OF|EMAILED|DEACTIVATED BY USER)\\b/i.test(line)) continue;
      if (/^\\d{{2,3}}:\\d{{3}}:\\d{{3}}\\b/.test(line)) continue;
      return line;
    }}
    return '';
  }}

  function getCourseCode(cardText) {{
    const match = cardText.match(/\\b(\\d{{2,3}}:\\d{{3}}:\\d{{3}})(?:\\s+(\\d{{1,2}}))?\\b/);
    return match ? (match[1] + (match[2] ? ' ' + match[2] : '')) : '';
  }}

  const courseNames = {{}};
  for (const index of Object.keys(activeCards)) {{
    const cardText = getCardText(index);
    const title = getCourseTitle(cardText);
    const code = getCourseCode(cardText);
    courseNames[index] = title && code ? title + '（' + code + '）' : (title || code);
  }}
  return JSON.stringify({{
    url: location.href,
    ready: document.readyState === 'complete',
    dashboard: activeMarker >= 0,
    term: body.includes('SPRING 2027'),
    activeIndexes: Object.keys(activeCards),
    activeCards,
    inactiveCards,
    courseNames,
    cards
  }});
}})()
"""
    return parse_page_json(safari_js(SCHEDRU_PREFIX, source))


def webreg_state() -> dict[str, Any]:
    source = r"""
(() => {
  const body = document.body?.innerText || '';
  const fields = Array.from(document.querySelectorAll('input[type="text"]'));
  const addButton = Array.from(document.querySelectorAll('button, input[type="submit"]'))
    .find(el => (el.innerText || el.value || '').trim().toLowerCase().includes('add courses'));
  const radioCount = document.querySelectorAll('input[type="radio"]').length;
  const isChooser = /\/chooseSemester\.htm$/i.test(location.pathname) ||
    (body.toLowerCase().includes('choose semester') && radioCount >= 4 && !addButton);
  return JSON.stringify({
    url: location.href,
    ready: document.readyState === 'complete',
    signedIn: body.includes('Logged in as') || body.includes('Log Out'),
    term: body.includes('Spring 2027'),
    fieldCount: fields.length,
    buttonFound: Boolean(addButton),
    chooseSemester: isChooser
  });
})()
"""
    return parse_page_json(safari_js(WEBREG_PREFIX, source))


def continue_with_spring_2027() -> str:
    source = r"""
(() => {
  const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
  const spring = radios.find(radio => {
    const labelText = [
      ...(radio.labels ? Array.from(radio.labels).map(label => label.innerText || label.textContent || '') : []),
      radio.getAttribute('aria-label') || '',
      radio.parentElement?.innerText || '',
      radio.parentElement?.parentElement?.innerText || '',
      radio.nextElementSibling?.innerText || radio.nextElementSibling?.textContent || '',
      radio.nextSibling?.textContent || '',
      radio.closest('label')?.innerText || ''
    ].join(' ').replace(/\s+/g, ' ').trim();
    return /spring\s+2027/i.test(labelText);
  });
  if (!spring) return 'STOP: Spring 2027 option not found.';
  if (!spring.checked) {
    spring.click();
    spring.checked = true;
    spring.dispatchEvent(new Event('input', {bubbles: true}));
    spring.dispatchEvent(new Event('change', {bubbles: true}));
  }
  const button = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"]'))
    .find(el => (el.innerText || el.value || '').trim().toLowerCase().includes('continue'));
  if (!button) return 'STOP: Continue button not found.';
  button.click();
  return 'CONTINUE_CLICKED';
})()
"""
    return safari_js(WEBREG_PREFIX, source)


def ensure_manage_registration(timeout: int = 40) -> dict[str, Any]:
    """Advance the signed-in chooser to Spring 2027, then require the add form."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = webreg_state()
        if not state.get("signedIn"):
            raise RuntimeError("WebReg 尚未登录；请在现有 Safari 标签页中手动登录。")
        if (state.get("ready") and state.get("term") and
                state.get("fieldCount", 0) >= 1 and state.get("buttonFound")):
            return state
        if state.get("chooseSemester"):
            result = continue_with_spring_2027()
            if not result.startswith("CONTINUE_CLICKED"):
                raise RuntimeError(result)
            logging.info("已在现有 WebReg 标签页选择 Spring 2027 并点击 Continue。")
            time.sleep(2)
            continue
        if state.get("ready"):
            raise RuntimeError(
                "WebReg 页面与预期不符；应为 Spring 2027 学期选择页或 Manage Registration。"
                f"页面状态：{state}"
            )
        time.sleep(1)
    raise RuntimeError("WebReg 未能返回 Spring 2027 的 Manage Registration 表单。")


def refresh_tab(url_prefix: str) -> None:
    safari_js(url_prefix, "location.reload(); 'reloaded'")


def submit_indexes(indexes: tuple[str, ...]) -> str:
    values = json.dumps(indexes)
    source = f"""
(() => {{
  const body = document.body?.innerText || '';
  const fields = Array.from(document.querySelectorAll('input[type="text"]'));
  const addButton = Array.from(document.querySelectorAll('button, input[type="submit"]'))
    .find(el => (el.innerText || el.value || '').trim().toLowerCase().includes('add courses'));
  const values = {values};
  if (!body.includes('Logged in as')) return 'STOP: WebReg session is no longer signed in.';
  if (!body.includes({json.dumps(TERM_LABEL)})) return 'STOP: Expected Spring 2027 page was not found.';
  if (fields.length < values.length || !addButton) return 'STOP: Could not find enough index fields and the Add Courses button.';
  for (let i = 0; i < fields.length; i++) {{
    const field = fields[i];
    field.focus();
    field.value = values[i] || '';
    field.dispatchEvent(new Event('input', {{bubbles: true}}));
    field.dispatchEvent(new Event('change', {{bubbles: true}}));
  }}
  addButton.click();
  return 'SUBMITTED: ' + values.join(', ');
}})()
"""
    result = safari_js(WEBREG_PREFIX, source)
    if not result.startswith("SUBMITTED:"):
        raise RuntimeError(result)
    return result.removeprefix("SUBMITTED: ")


def wait_for_registration_result(indexes: tuple[str, ...], timeout: int = 25) -> str:
    """Wait for WebReg's response and cancel any prompt requiring extra input."""
    read_result = r"""
(() => JSON.stringify({
  body: (document.body?.innerText || '').replace(/\s+/g, ' ').trim(),
  ready: document.readyState === 'complete'
}))()
"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = parse_page_json(safari_js(WEBREG_PREFIX, read_result))
        body = state.get("body", "")
        if "Additional input needed" in body:
            cancel = r"""
(() => {
  const button = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"]'))
    .find(el => (el.innerText || el.value || '').trim().toLowerCase() === 'cancel');
  if (button) { button.click(); return 'CANCELED_EXTRA_INPUT'; }
  return 'EXTRA_INPUT_NO_CANCEL_BUTTON';
})()
"""
            return safari_js(WEBREG_PREFIX, cancel) or "EXTRA_INPUT"
        registered = [index for index in indexes if f"[{index}]" in body]
        if registered:
            return "REGISTERED: " + ", ".join(registered)
        if any(f"Canceled action for {index}" in body for index in indexes):
            return "CANCELED: WebReg reports the action was canceled."
        if state.get("ready") and "Transaction Summary" in body:
            summary_start = body.find("Transaction Summary")
            summary = body[summary_start:summary_start + 300]
            return "SUMMARY: " + summary
        time.sleep(1)
    return "UNKNOWN: no final registration result appeared before timeout."


def terminal_commands(commands: queue.Queue[str]) -> None:
    """Read T/Q commands without blocking the monitoring loop."""
    while True:
        try:
            line = sys.stdin.readline()
        except Exception:
            return
        if not line:
            return
        commands.put(line.strip().lower())


def ready_schedru(state: dict[str, Any]) -> bool:
    active_cards = state.get("activeCards", {})
    return (
        state.get("ready")
        and state.get("dashboard")
        and state.get("term")
        and all(status in {"open", "opened-notified", "closed"}
                for status in active_cards.values())
    )


def course_status_label(status: str | None) -> str:
    return {
        "closed": "关闭中",
        "open": "已开放",
        "opened-notified": "已收到开放通知",
        "inactive": "已停用",
        "unknown": "状态未识别",
    }.get(status or "", status or "状态未识别")


def format_courses(state: dict[str, Any], indexes: set[str] | None = None) -> str:
    selected = indexes if indexes is not None else set(state.get("activeIndexes", []))
    names = state.get("courseNames", {})
    statuses = state.get("cards", {})
    if not selected:
        return "（当前没有 active 课程）"
    return "\n".join(
        f"  • {names.get(index) or '课程名称暂未识别'}｜index {index}｜{course_status_label(statuses.get(index))}"
        for index in sorted(selected)
    )


def wait_for_schedru_state(timeout: int = 30) -> dict[str, Any]:
    """Wait through page loads before deciding the dashboard is unavailable."""
    deadline = time.monotonic() + timeout
    last_issue = "no dashboard state returned"
    while time.monotonic() < deadline:
        try:
            state = schedru_state()
            if ready_schedru(state):
                return state
            last_issue = f"dashboard/card state was incomplete: {state}"
        except Exception as exc:
            last_issue = str(exc)
        time.sleep(1)
    raise RuntimeError(f"Schedru did not become ready within {timeout}s. Last observation: {last_issue}")


def main() -> int:
    if sys.platform != "darwin":
        logging.error("此监听程序需要在 macOS 的 Safari 中运行。")
        return 2

    try:
        schedru = wait_for_schedru_state()
        webreg = ensure_manage_registration()
    except KeyboardInterrupt:
        logging.info("页面准备过程中收到停止指令，程序已退出。")
        return 130
    except Exception as exc:
        logging.error("无法准备现有的 WebReg 页面：%s", exc)
        return 2

    if not ready_schedru(schedru):
        logging.error("Schedru 没有显示可读取的 Spring 2027 Active Snipes 列表：%s", schedru)
        return 2
    if not (webreg.get("ready") and webreg.get("signedIn") and webreg.get("term")
            and webreg.get("fieldCount", 0) >= 1 and webreg.get("buttonFound")):
        logging.error("现有 Safari 会话中的 WebReg 尚未就绪：%s", webreg)
        return 2

    active_indexes = set(schedru.get("activeIndexes", []))
    tracked_indexes = set(active_indexes)
    tracked_course_names = {
        index: name for index, name in schedru.get("courseNames", {}).items() if name
    }
    last_statuses = dict(schedru.get("cards", {}))
    logging.info("目前正在监听这些课程：\n%s", format_courses(schedru, active_indexes))
    logging.info("现有 Safari WebReg 标签页已登录并就绪。")
    logging.info("输入 T 并回车：真实提交当前 active 列表中的第一门课；输入 Q 并回车：停止。")

    last_schedru_refresh = time.monotonic()
    last_webreg_keepalive = time.monotonic()
    last_schedru_warning = 0.0
    commands: queue.Queue[str] = queue.Queue()
    threading.Thread(target=terminal_commands, args=(commands,), daemon=True).start()

    try:
        while True:
            command = None
            try:
                command = commands.get_nowait()
            except queue.Empty:
                pass
            if command == "q":
                logging.info("已由用户停止监听。")
                return 130
            if command == "t":
                try:
                    current = wait_for_schedru_state(timeout=15)
                    candidates = sorted(current.get("activeIndexes", []))
                    if not candidates:
                        logging.warning("未执行手动测试：当前没有列出的 active 课程 index。")
                    else:
                        test_index = candidates[0]
                        ensure_manage_registration()
                        test_name = current.get("courseNames", {}).get(test_index) or "课程名称暂未识别"
                        logging.info("手动真实提交测试：%s（index %s）。", test_name, test_index)
                        submitted = submit_indexes((test_index,))
                        result = wait_for_registration_result((test_index,))
                        logging.info("已提交测试 index %s。WebReg 结果：%s", submitted, result)
                        logging.info("手动提交尝试结束，监听程序已停止。")
                        return 0
                except Exception as exc:
                    logging.warning("无法执行手动测试，继续监听：%s", exc)

            schedru = None
            schedru_issue = ""
            try:
                observed = schedru_state()
                if ready_schedru(observed):
                    schedru = observed
                else:
                    schedru_issue = f"incomplete dashboard/cards: {observed}"
            except Exception as exc:
                schedru_issue = str(exc)

            if schedru is None:
                now = time.monotonic()
                if now - last_schedru_warning >= 60:
                    logging.warning("Schedru 暂时不可用，将继续重试：%s", schedru_issue)
                    last_schedru_warning = now
                if now - last_schedru_refresh >= SCHEDRU_REFRESH_SECONDS:
                    try:
                        refresh_tab(SCHEDRU_PREFIX)
                        last_schedru_refresh = time.monotonic()
                        logging.info("已刷新 Schedru，继续恢复页面状态。")
                    except Exception as exc:
                        logging.debug("Schedru refresh retry failed: %s", exc)
                time.sleep(POLL_SECONDS)
                continue

            statuses = schedru["cards"]
            current_active = set(schedru.get("activeIndexes", []))
            tracked_course_names.update({
                index: name for index, name in schedru.get("courseNames", {}).items() if name
            })
            newly_active = current_active - active_indexes
            removed_from_active = active_indexes - current_active
            if newly_active or removed_from_active:
                logging.info("Active Snipes 列表已变化，现在监听：\n%s",
                             format_courses(schedru, current_active))
            tracked_indexes.update(current_active)
            active_indexes = current_active

            previous_statuses = last_statuses
            changed = {index: status for index, status in statuses.items()
                       if status != last_statuses.get(index)}
            if changed:
                changed_lines = [
                    f"{schedru.get('courseNames', {}).get(index) or tracked_course_names.get(index) or '课程名称暂未识别'}（index {index}）：{course_status_label(status)}"
                    for index, status in changed.items()
                ]
                logging.info("课程状态更新：%s", "；".join(changed_lines))

            active_open = [index for index in sorted(current_active)
                           if statuses.get(index) == "open"]
            notified_open = [index for index in sorted(tracked_indexes)
                             if statuses.get(index) == "opened-notified"
                             and previous_statuses.get(index) == "closed"]
            opened = active_open + notified_open
            if opened:
                trigger_index = opened[0]
                # Confirm the opening signal remains visible before submitting this one index.
                time.sleep(2)
                try:
                    confirmed = wait_for_schedru_state(timeout=15)
                except Exception as exc:
                    logging.warning("暂时无法确认课程已开放，继续监听：%s", exc)
                    time.sleep(POLL_SECONDS)
                    continue
                if confirmed["cards"].get(trigger_index) not in {"open", "opened-notified"}:
                    logging.info("确认时开放状态已消失，继续监听。")
                    last_statuses = dict(confirmed["cards"])
                else:
                    ensure_manage_registration()
                    trigger_name = (confirmed.get("courseNames", {}).get(trigger_index)
                                    or tracked_course_names.get(trigger_index)
                                    or "课程名称暂未识别")
                    logging.info("检测到课程开放：%s（index %s）；只提交这一门课。",
                                 trigger_name, trigger_index)
                    submitted = submit_indexes((trigger_index,))
                    result = wait_for_registration_result((trigger_index,))
                    logging.info("index %s 的 WebReg 结果：%s", submitted, result)
                    logging.info("注册提交尝试结束，监听程序已停止。")
                    return 0
            else:
                last_statuses = dict(statuses)

            now = time.monotonic()
            if now - last_schedru_refresh >= SCHEDRU_REFRESH_SECONDS:
                refresh_tab(SCHEDRU_PREFIX)
                last_schedru_refresh = time.monotonic()
                logging.info("已刷新现有的 Schedru 仪表板。")
            if now - last_webreg_keepalive >= WEBREG_KEEPALIVE_SECONDS:
                webreg = webreg_state()
                if not webreg.get("signedIn"):
                    raise RuntimeError("WebReg 会话已失效；程序停止，不会尝试代替你登录。")
                refresh_tab(WEBREG_PREFIX)
                last_webreg_keepalive = time.monotonic()
                ensure_manage_registration()
                logging.info("已刷新 WebReg，并返回 Spring 2027 Manage Registration。")
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        logging.info("已由用户停止监听。")
        return 130
    except Exception as exc:
        logging.error("监听程序已停止：%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
