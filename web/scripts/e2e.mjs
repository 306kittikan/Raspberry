// ============================================================
// ขับหน้าจอตู้จริงผ่านเบราว์เซอร์ แล้วตรวจว่าแต่ละหน้าแสดงสิ่งที่ควรแสดง
//
//   1) รัน API   :  cd server && .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
//   2) รันหน้าเว็บ:  cd web && npm run dev
//   3) รันสคริปต์ :  cd web && node scripts/e2e.mjs [--headed] [--shots ./shots]
//
// ใช้ Chrome/Chromium ที่ติดตั้งอยู่ในเครื่อง ไม่ดาวน์โหลดเบราว์เซอร์เพิ่ม
// ============================================================

import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright-core'

const args = process.argv.slice(2)
const flag = (name, fallback = null) => {
  const i = args.indexOf(name)
  return i === -1 ? fallback : args[i + 1] ?? true
}

const BASE = flag('--base', 'http://localhost:5173')
const SHOTS = flag('--shots', null)
const HEADED = args.includes('--headed')

// จอตู้เป็นแนวตั้ง 1080×1920 ย่อครึ่งหนึ่งให้พอดีจอคอมพิวเตอร์ขณะทดสอบ
const VIEWPORT = { width: 540, height: 960 }

const results = []
const check = (ok, name, detail = '') => {
  results.push({ ok, name })
  console.log(`  [${ok ? 'ผ่าน' : 'ไม่ผ่าน'}] ${name}${detail ? ` — ${detail}` : ''}`)
}

if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true })

const launchOptions = { headless: !HEADED }
let browser
for (const channel of ['chrome', 'msedge', 'chromium']) {
  try {
    browser = await chromium.launch({ ...launchOptions, channel })
    break
  } catch {
    // ลองเบราว์เซอร์ตัวถัดไป
  }
}
if (!browser) {
  console.error('ไม่พบ Chrome, Edge หรือ Chromium ในเครื่อง')
  process.exit(2)
}

const page = await browser.newPage({ viewport: VIEWPORT })
const errors = []
const faceCalls = []
page.on('response', (r) => {
  if (r.url().includes('/api/face/') || r.url().includes('/api/me/face')) {
    faceCalls.push({ status: r.status(), path: r.url().split('/api')[1].split('?')[0] })
  }
})
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(`console: ${m.text()}`)
})

const shot = async (name) => {
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`) })
}
const body = async () => (await page.locator('body').innerText()).replace(/\s+/g, ' ')

try {
  console.log('1. หน้าจอพัก')
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
  let text = await body()
  check(text.includes('สาขาวิชาวิทยาการคอมพิวเตอร์'), 'แสดงชื่อสาขาจากฐานข้อมูล')
  check(text.includes('ยืนหน้าตู้เพื่อดูตารางเรียนของคุณ'), 'แสดงข้อความเชิญชวน')
  check(/25\d{2}/.test(text), 'แสดงวันที่แบบพุทธศักราช')
  check(!/\b6604\d{6}\b/.test(text), 'ไม่มีรหัสนักศึกษาปรากฏก่อนยืนยันตัวตน')
  await shot('1-idle')

  console.log('\n2. สแกนใบหน้าด้วยกล้องจริง')
  await page.getByText('เริ่มสแกนใบหน้า').click()
  await page.waitForTimeout(1500)
  check((await body()).includes('กำลังตรวจจับใบหน้า'), 'แสดงสถานะกำลังตรวจจับ')
  check((await page.locator('img[src*="/api/face/stream"]').count()) > 0,
        'แสดงภาพสดจากกล้องจริง')
  await shot('2-scan')

  // ไม่มีใครยืนหน้ากล้องระหว่างทดสอบอัตโนมัติ ระบบจึงต้องหมดเวลาแล้วเสนอทางเลือกอื่น
  // นี่คือพฤติกรรมที่ถูกต้องของกล้องจริง ไม่ใช่ความล้มเหลวของการทดสอบ
  await page.getByText('ใช้งานแบบไม่ระบุตัวตน').waitFor({ timeout: 25000 })
  text = await body()
  check(text.includes('กรอกรหัสนักศึกษา'), 'หาใบหน้าไม่เจอภายใน 10 วินาที → เสนอทางเลือกอื่น')
  check(text.includes('ใช้งานแบบไม่ระบุตัวตน'), 'มีทางเลือกใช้งานแบบไม่ระบุตัวตน')
  await shot('3-notrecognized')

  console.log('\n2ก. เข้าสู่ระบบด้วยรหัสนักศึกษา')
  await page.getByText('ใช้แป้นตัวเลขบนหน้าจอ').click()
  await page.waitForTimeout(700)
  for (const digit of '6604101001') {
    await page.getByRole('button', { name: digit, exact: true }).first().click()
  }
  await page.getByRole('button', { name: 'ตกลง', exact: true }).click()
  await page.waitForTimeout(2200)

  console.log('\n3. หน้าหลักส่วนตัว')
  text = await body()
  check(text.includes('••••'), 'แสดงรหัสนักศึกษาแบบปิดบังเท่านั้น')
  check(!/\b6604\d{6}\b/.test(text), 'ไม่มีรหัสนักศึกษาเต็มบนหน้าจอ')
  check(/10301\d{3}/.test(text), 'แสดงรหัสวิชาจริงของคาบถัดไป')
  check(text.includes('ข้อมูลอัปเดตล่าสุด'), 'แสดงวันที่อัปเดตข้อมูล')
  check(text.includes('ข้อมูลจากระบบของสาขา'), 'ติดป้ายบอกแหล่งที่มาของข้อมูล')
  check(text.includes('ตารางเรียนเป็นข้อมูลตัวอย่าง'),
        'เตือนผู้ใช้ว่าตารางเรียนยังไม่ใช่ของจริง')
  check(/Lab \d|Lect \d|Lab Network/.test(text), 'แสดงห้องเรียนจริงของสาขา')
  await shot('4-home')

  console.log('\n4. แท็บทั้งสัปดาห์และกำหนดสอบ')
  await page.getByRole('button', { name: 'ทั้งสัปดาห์' }).click()
  await page.waitForTimeout(500)
  text = await body()
  check(text.includes('วันจันทร์') && text.includes('วันศุกร์'), 'ตารางทั้งสัปดาห์ครบจันทร์–ศุกร์')
  await shot('5-week')

  await page.getByRole('button', { name: 'กำหนดสอบ' }).click()
  await page.waitForTimeout(500)
  check((await body()).includes('สอบกลางภาค'), 'แสดงกำหนดสอบ')
  await shot('6-exam')

  console.log('\n5. ผู้ช่วยตอบคำถาม')
  await page.getByText('ถามผู้ช่วย').first().click()
  await page.waitForTimeout(800)
  check((await body()).includes('คำถามยอดนิยม'), 'แสดงคำถามยอดนิยมจากฐานข้อมูล')
  await shot('7-assistant')

  await page.getByText('คาบต่อไปเรียนที่ไหน').click()
  await page.waitForTimeout(2500)
  text = await body()
  check(text.includes('คาบเรียนถัดไปของคุณ') || text.includes('คาบที่กำลังเรียนอยู่'),
        'ตอบคำถามตารางเรียนได้')
  check(text.includes('ข้อมูลจากระบบของสาขา'), 'คำตอบมีป้ายบอกที่มา (ฐานข้อมูล)')
  await shot('8-answer')

  await page.getByText('ติดต่ออาจารย์ที่ไหน').click()
  await page.waitForTimeout(2000)
  text = await body()
  check(/@mju\.ac\.th/.test(text), 'ตอบด้วยอีเมลจริงของบุคลากรสาขา')
  await shot('8b-teacher')

  await page.getByText('ทุนวิจัยระดับปริญญาตรีมีเท่าไร').click()
  await page.waitForTimeout(2000)
  text = await body()
  check(text.includes('ไม่พบข้อมูลนี้ในระบบ'), 'คำถามที่ไม่มีเอกสารอ้างอิง → ไม่เดาคำตอบ')
  check(text.includes('cs@mju.ac.th'), 'เสนอช่องทางติดต่อสาขาแทน')
  await shot('9-notfound')

  console.log('\n5ก. ลงทะเบียนใบหน้า')
  // เส้นทางนี้เคยพังด้วย 401 เพราะระบบยังไม่รู้ว่ากำลังลงทะเบียนให้ใคร
  // ตอนนี้ต้องผ่านการกรอกรหัสนักศึกษาก่อนเสมอ
  await page.getByRole('button', { name: /ออกจากระบบ/ }).click()
  await page.waitForTimeout(1200)
  await page.evaluate(() => fetch('/api/sim/face/unknown', { method: 'POST' }))
  await page.waitForTimeout(1300)

  await page.getByText('ลงทะเบียนใบหน้า').first().click()
  await page.waitForTimeout(800)
  check((await body()).includes('ยืนยันตัวตนก่อนลงทะเบียนใบหน้า'),
        'ลงทะเบียนต้องระบุตัวตนด้วยรหัสนักศึกษาก่อน')

  for (const digit of '6604101388') {
    await page.getByRole('button', { name: digit, exact: true }).first().click()
  }
  await page.getByRole('button', { name: 'ตกลง', exact: true }).click()
  await page.waitForTimeout(2200)
  check((await body()).includes('ให้ความยินยอมในการเก็บข้อมูล'),
        'ระบุตัวตนแล้วเข้าสู่หน้าขอความยินยอม')

  await page.getByText('ข้าพเจ้า', { exact: false }).first().click()
  await page.waitForTimeout(500)
  await page.getByRole('button', { name: /เริ่มถ่ายใบหน้า/ }).click()
  await page.waitForTimeout(3000)
  text = await body()
  check(text.includes('กำลังถ่ายใบหน้า'), 'เริ่มเก็บตัวอย่างใบหน้าได้')
  check((await page.locator('img[src*="/api/face/stream"]').count()) > 0,
        'หน้าถ่ายใบหน้าแสดงภาพจากกล้อง')

  const denied = faceCalls.filter((c) => c.status === 401 || c.status === 403)
  check(denied.length === 0, 'ไม่มีคำขอใดถูกปฏิเสธสิทธิ์ระหว่างลงทะเบียน',
        denied.map((c) => `${c.status} ${c.path}`).join(', '))
  check(faceCalls.some((c) => c.path === '/face/consent' && c.status === 200),
        'บันทึกความยินยอมลงฐานข้อมูลสำเร็จ')
  check(faceCalls.some((c) => c.path === '/face/enroll/start' && c.status === 200),
        'เซิร์ฟเวอร์เริ่มเก็บเวกเตอร์ใบหน้าแล้ว')
  await shot('11-enroll')

  await page.getByRole('button', { name: 'ยกเลิก' }).click()
  await page.waitForTimeout(1300)

  console.log('\n6. ออกจากระบบแล้วข้อมูลต้องหายจากจอ')
  // ออกจากระบบไปแล้วตอนเริ่มหมวด 5ก และกดยกเลิกจากหน้าถ่ายใบหน้าแล้ว
  // จึงควรอยู่ที่หน้าจอพักโดยไม่มีข้อมูลผู้ใช้ค้างอยู่
  text = await body()
  check(text.includes('ยืนหน้าตู้เพื่อดูตารางเรียนของคุณ'), 'กลับสู่หน้าจอพัก')
  check(!text.includes('••••'), 'ไม่มีข้อมูลผู้ใช้ค้างบนหน้าจอ')
  await shot('10-logged-out')

  console.log('\n7. โหมดจอคอมพิวเตอร์แนวนอน (Windows)')
  await page.setViewportSize({ width: 1600, height: 900 })
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1800)
  const desktop = await page.evaluate(() => ({
    noHScroll: document.body.scrollWidth <= window.innerWidth,
    hasAside: Boolean(document.querySelector('img[src*="/api/face/stream"]')),
    stageFound: Boolean(document.querySelector('[style*="1080px"]')),
  }))
  check(desktop.stageFound, 'เวทีขนาดตู้ยังคงขนาด 1080 บนจอแนวนอน')
  check(desktop.hasAside, 'แผงด้านข้างแสดงภาพผู้ใช้จากกล้อง')
  check(desktop.noHScroll, 'ไม่มีแถบเลื่อนแนวนอน')
  await shot('12-desktop')

  check(errors.length === 0, 'ไม่มีข้อผิดพลาดใน console',
        errors.length ? [...new Set(errors)].slice(0, 3).join(' / ') : '')
} finally {
  await browser.close()
}

const failed = results.filter((r) => !r.ok)
console.log(`\n${'='.repeat(52)}`)
console.log(`ผ่าน ${results.length - failed.length}/${results.length} ข้อ`)
failed.forEach((r) => console.log(`  ไม่ผ่าน: ${r.name}`))
process.exit(failed.length ? 1 : 0)
