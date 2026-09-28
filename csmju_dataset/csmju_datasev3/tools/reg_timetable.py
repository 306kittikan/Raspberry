"""Parse reg.mju.ac.th weekly timetable grids (teach_time / learn_time). Also usable on-demand."""
import re, html, requests
R = 'https://reg.mju.ac.th/registrar/'
DAYS = ['จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์', 'เสาร์', 'อาทิตย์']

def sess():
    S = requests.Session(); S.headers['User-Agent'] = 'Mozilla/5.0 (CSMJU student dataset project)'
    S.get(R + 'home.asp', timeout=60); return S
def dec(r): return r.content.decode('tis-620', errors='replace')
def enc(d): return {k: (v.encode('tis-620') if isinstance(v, str) else v) for k, v in d.items()}
def clean(s): return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or '').replace('\xa0', ' '))).strip()

def parse_grid(s):
    """Return list of sessions from a timetable grid page. Each hour column = COLSPAN 12 (5-minute units)."""
    hdr = re.search(r'Day/Time.*?</TR>', s, re.S)
    if not hdr: return []
    times = re.findall(r'(\d{1,2}):(\d\d)-\d{1,2}:\d\d', hdr.group(0))
    if not times: return []
    base = int(times[0][0]) * 60 + int(times[0][1])
    out = []
    rows = re.findall(r'<TR BGCOLOR=#F0F0F0>(.*?)</TR>', s[hdr.end():], re.S)
    for tr in rows:
        cells = re.findall(r'<TD([^>]*)>(.*?)(?=<TD|$)', tr, re.S)
        if not cells: continue
        day = clean(cells[0][1])
        if day not in DAYS: continue
        pos = 0
        for attrs, body in cells[1:]:
            m = re.search(r'COLSPAN=(\d+)', attrs, re.I)
            n = int(m.group(1)) if m else 0
            if 'class_info_2' in body:
                start = base + pos * 5; end = start + n * 5
                code = clean(re.search(r'<font face=tahoma>(.*?)</a>', body, re.S | re.I).group(1))
                title = re.search(r'TITLE="([^"]*)"', body)
                parts = [clean(x) for x in re.split(r'<BR>', body, flags=re.I)]
                info = parts[1] if len(parts) > 1 else ''          # "(3) 1, Lab คอม 5"
                bld = parts[2] if len(parts) > 2 else None
                mi = re.match(r'\((\d+)\)\s*(\d+),\s*(.*)', info)
                cid = re.search(r'courseid=(\d+)', body)
                out.append({'day_th': day, 'weekday_index': DAYS.index(day), 'start': f'{start // 60:02d}:{start % 60:02d}',
                            'end': f'{end // 60:02d}:{end % 60:02d}', 'course_code': code,
                            'title_th': title.group(1).split(':')[0].strip() if title else None,
                            'credits': int(mi.group(1)) if mi else None, 'section': int(mi.group(2)) if mi else None,
                            'room': mi.group(3).strip() if mi else info, 'building': bld, 'courseid': cid.group(1) if cid else None})
            pos += n
    return out

def find_instructor(S, name):
    s = dec(S.post(R + 'teach_time.asp', data=enc({'f_cmd': '1', 'f_officername': name, 'f_maxrows': '50'}), timeout=60))
    res = []
    for h, t in re.findall(r'<a\s[^>]*?href=["\']?(teach_time\.asp\?officerid[^"\'\s>]*)["\']?[^>]*>(.*?)</a>', s, re.S | re.I):
        res.append({'url': html.unescape(h), 'name': clean(t), 'officerid': re.search(r'officerid=(\d+)', h).group(1),
                    'email': (re.search(r'officeremail=([^&]*)', h).group(1).replace('%40', '@').replace('%2E', '.') if 'officeremail=' in h else None)})
    return res

def instructor_timetable(S, officer_url, acadyear=None, semester=None):
    u = R + officer_url + (f'&acadyear={acadyear}&semester={semester}' if acadyear else '')
    s = dec(S.get(u, timeout=60)); return parse_grid(s), s

def student_timetable(student_code, acadyear=None, semester=None):
    """On-demand lookup for ONE student (e.g. the app user themself). Does not store anything."""
    S = sess()
    s = dec(S.post(R + 'learn_time.asp', data=enc({'f_cmd': '1', 'f_studentcode': student_code, 'f_studentname': '', 'f_studentsurname': '',
                                                   'f_studentstatus': '', 'f_maxrows': '25'}), timeout=60))
    m = re.search(r'href=["\']?(learn_time\.asp\?[^"\'\s>]*studentid[^"\'\s>]*)', s, re.I)
    if not m: return {'student_code': student_code, 'sessions': [], 'error': 'not found'}
    u = R + html.unescape(m.group(1)) + (f'&acadyear={acadyear}&semester={semester}' if acadyear else '')
    page = dec(S.get(u, timeout=60))
    return {'student_code': student_code, 'sessions': parse_grid(page)}
