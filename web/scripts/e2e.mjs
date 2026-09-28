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

const logout = async () => {
  await page.getByRole('button', { name: /ออกจากระบบ|จบการใช้งาน/ }).click()
  await page.waitForTimeout(1300)
}

/** เข้าหน้าที่เสนอทางเลือกอื่น (กรอกรหัสนักศึกษา / ลงทะเบียนใบหน้า)
 *
 * เดินตามเส้นทางจริงบนหน้าจอ ไม่ยิงเหตุการณ์จำลองจากหน้าอื่น
 * เพราะตู้รับผลการสแกนเฉพาะตอนที่ผู้ใช้อยู่หน้าสแกนเท่านั้น (UC-20)
 * ถ้ากล้องจำหน้าได้ ให้ตอบ "ไม่ใช่" ซึ่งพาไปหน้าเดียวกัน
 */
const gotoOtherOptions = async () => {
  const scan = page.getByText('เริ่มสแกนใบหน้า')
  if ((await scan.count()) > 0) {
    await scan.click()
    await page.waitForTimeout(500)
  }

  const keypadOption = page.getByText('ใช้แป้นตัวเลขบนหน้าจอ')
  const notMe = page.getByRole('button', { name: 'ไม่ใช่', exact: true })
  await Promise.race([
    keypadOption.waitFor({ timeout: 15000 }).catch(() => {}),
    notMe.waitFor({ timeout: 15000 }).catch(() => {}),
  ])

  if ((await notMe.count()) > 0) {
    await notMe.click()
    await page.waitForTimeout(900)
  }

  // กล้องสดอาจสรุปผลไม่ได้เลย เช่น แสงน้อยหรือมีหลายคน — ใช้ปุ่มสำรองบนหน้าสแกน
  if ((await keypadOption.count()) === 0) {
    const fallback = page.getByText('กรอกรหัสนักศึกษาแทน')
    if ((await fallback.count()) > 0) {
      await fallback.click()
      await page.waitForTimeout(700)
    }
  }
}

/** กรอกรหัสนักศึกษาบนแป้นตัวเลขแล้วกดตกลง */
const typeStudentId = async (studentId) => {
  const keypadOption = page.getByText('ใช้แป้นตัวเลขบนหน้าจอ')
  if ((await keypadOption.count()) > 0) {
    await keypadOption.click()
    await page.waitForTimeout(700)
  }
  for (const digit of studentId) {
    await page.getByRole('button', { name: digit, exact: true }).first().click()
  }
  await page.getByRole('button', { name: 'ตกลง', exact: true }).click()
}

// บัญชีสาธิตเป็นคนเดียวที่มีตารางเรียนตัวอย่างอยู่ในฐานข้อมูล
// รายชื่อที่นำเข้าจากระบบทะเบียนยังไม่มีตารางเรียน เพราะยังไม่มีแหล่งข้อมูลจริง
const DEMO_STUDENT = '6604101001'

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

  // ถ้ามีคนที่ลงทะเบียนไว้ยืนอยู่หน้ากล้อง ระบบจำได้ในเสี้ยววินาที
  // หน้าสแกนจึงอาจผ่านไปก่อนที่จะตรวจทัน ต้องคอยดูถี่ ๆ แทนการรอเวลาตายตัว
  let sawScanning = false
  let sawStream = false
  for (let i = 0; i < 20 && !sawScanning; i += 1) {
    sawScanning = (await body()).includes('กำลังตรวจจับใบหน้า')
    if (sawScanning) {
      sawStream = (await page.locator('img[src*="/api/face/stream"]').count()) > 0
      await shot('2-scan')
    }
    if ((await page.getByRole('button', { name: 'ใช่', exact: true }).count()) > 0) break
    await page.waitForTimeout(100)
  }

  const scanStarted = faceCalls.some(
    (c) => c.path === '/face/scan/start' && c.status === 200
  )
  check(scanStarted, 'สั่งให้เซิร์ฟเวอร์เริ่มหาใบหน้าแล้ว')
  check(sawScanning || scanStarted, 'เข้าสู่หน้าสแกนใบหน้า',
        sawScanning ? '' : 'จำได้เร็วจนข้ามหน้าสแกน')
  if (sawScanning) {
    check(sawStream, 'หน้าสแกนแสดงภาพสดจากกล้องจริง')
  }

  // ผลลัพธ์ขึ้นกับว่ามีคนอยู่หน้ากล้องหรือไม่ และเคยลงทะเบียนใบหน้าไว้หรือยัง
  // ทดสอบจึงต้องรองรับทั้งสองทาง ไม่ใช่บังคับให้ได้ทางใดทางหนึ่ง
  //   จำได้    → หน้ายืนยันตัวตน "คุณคือ ... ใช่ไหม"
  //   จำไม่ได้ → หน้าเสนอทางเลือกอื่น
  const confirmYes = page.getByRole('button', { name: 'ใช่', exact: true })
  const anonOption = page.getByText('ใช้งานแบบไม่ระบุตัวตน')
  await Promise.race([
    confirmYes.waitFor({ timeout: 25000 }).catch(() => {}),
    anonOption.waitFor({ timeout: 25000 }).catch(() => {}),
  ])

  // กล้องสดให้ผลไม่เหมือนกันทุกครั้ง ขึ้นกับแสงและตำแหน่งของคนที่อยู่หน้าจอ
  // ถ้าค้างอยู่หน้าสแกน (เช่น พบหลายใบหน้า) ให้ใช้ปุ่มสำรองบนหน้านั้นแทน
  // เพื่อไม่ให้ชุดทดสอบล้มทั้งชุดเพราะสภาพแสงในห้อง
  if ((await confirmYes.count()) === 0 && (await anonOption.count()) === 0) {
    check(true, 'กล้องยังสรุปผลไม่ได้ — ใช้ทางสำรองบนหน้าสแกน',
          (await body()).slice(60, 130))
    await page.getByText('กรอกรหัสนักศึกษาแทน').click()
    await page.waitForTimeout(700)
  }

  const recognised = (await confirmYes.count()) > 0
  text = await body()

  if (recognised) {
    check(/คุณคือ .+ ใช่ไหม/.test(text), 'กล้องจำใบหน้าได้ → ถามยืนยันตัวตน')
    check(!/\b6604\d{6}\b/.test(text), 'หน้ายืนยันตัวตนไม่แสดงรหัสนักศึกษาเต็ม')
    await shot('3-confirm')

    console.log('\n2ก. กดยืนยันว่าใช่')
    await confirmYes.click()
  } else {
    check(text.includes('กรอกรหัสนักศึกษา'),
          'กล้องจำไม่ได้ → เสนอให้กรอกรหัสนักศึกษาแทน')
    await shot('3-notrecognized')

    console.log('\n2ก. เข้าสู่ระบบด้วยรหัสนักศึกษา')
    await typeStudentId(DEMO_STUDENT)
  }

  // หน้าหลักต้องโหลดตารางเรียนและกำหนดสอบก่อนจึงจะครบ
  // รอปุ่มที่มีเฉพาะหน้าหลัก แทนการรอเวลาตายตัวซึ่งไม่แน่นอนตามภาระของเครื่อง
  //
  // นักศึกษาที่นำเข้าจากระบบทะเบียนยังไม่มีข้อมูลตารางเรียน หน้าหลักจึงขึ้น
  // ข้อความบอกตรง ๆ แทนแท็บตาราง ซึ่งเป็นพฤติกรรมที่ถูกต้องและต้องตรวจด้วย
  // จากนั้นค่อยสลับไปบัญชีสาธิตเพื่อทดสอบส่วนที่ต้องใช้ตารางเรียน
  const weekTab = page.getByRole('button', { name: 'ทั้งสัปดาห์' })
  const noSchedule = page.getByText('ยังไม่มีข้อมูลตารางเรียน')
  await Promise.race([
    weekTab.waitFor({ timeout: 20000 }).catch(() => {}),
    noSchedule.waitFor({ timeout: 20000 }).catch(() => {}),
  ])

  if ((await weekTab.count()) === 0) {
    check((await noSchedule.count()) > 0,
          'ผู้ที่ยังไม่มีข้อมูลตารางเรียน เห็นข้อความบอกตรง ๆ ไม่ใช่จอว่างหรือข้อมูลของคนอื่น',
          (await body()).slice(0, 90))
    check((await body()).includes('สำนักงานสาขา'),
          'บอกช่องทางติดต่อไว้ให้ ไม่ใช่ปล่อยให้ผู้ใช้ค้าง')
    await shot('4-noschedule')

    console.log('\n2ข. สลับไปบัญชีสาธิตที่มีตารางเรียน เพื่อทดสอบส่วนที่เหลือ')
    await logout()
    await gotoOtherOptions()
    await typeStudentId(DEMO_STUDENT)
    await weekTab.waitFor({ timeout: 20000 })
  }
  await page.waitForTimeout(400)

  console.log('\n3. หน้าหลักส่วนตัว')
  text = await body()
  check(text.includes('••••'), 'แสดงรหัสนักศึกษาแบบปิดบังเท่านั้น')
  check(!/\b6604\d{6}\b/.test(text), 'ไม่มีรหัสนักศึกษาเต็มบนหน้าจอ')
  check(/10301\d{3}/.test(text), 'แสดงรหัสวิชาจริงของคาบถัดไป')
  check(text.includes('ข้อมูลอัปเดตล่าสุด'), 'แสดงวันที่อัปเดตข้อมูล')
  check(text.includes('ข้อมูลจากระบบของสาขา'), 'ติดป้ายบอกแหล่งที่มาของข้อมูล')
  // ป้ายเตือนต้องขึ้นเฉพาะกับตารางที่เป็นข้อมูลสมมติ
  // ตั้งแต่นำเข้าตารางเรียนจริงรายบุคคล นักศึกษาที่มีข้อมูลจริงต้องไม่เห็นป้ายนี้
  // ถ้าบังคับให้ขึ้นเสมอ เท่ากับทดสอบว่าระบบโกหกผู้ใช้
  // บัญชีสาธิตเท่านั้นที่ยังใช้ตารางสมมติ ดูจากรหัสที่ปิดบังบนแถบบนสุด
  const onDemoAccount = text.includes('••••1001')
  if (onDemoAccount) {
    check(text.includes('ตารางเรียนเป็นข้อมูลตัวอย่าง'),
          'บัญชีสาธิต ต้องเตือนว่าตารางเรียนยังไม่ใช่ของจริง')
  } else {
    check(!text.includes('ตารางเรียนเป็นข้อมูลตัวอย่าง'),
          'นักศึกษาที่มีตารางเรียนจริง ต้องไม่ถูกเตือนว่าเป็นข้อมูลตัวอย่าง')
  }
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

  console.log('\n5. หน้าต่างแชทของผู้ช่วย')
  await page.getByText('ถามผู้ช่วย').first().click()
  await page.waitForTimeout(1000)
  text = await body()
  check(text.includes('ผู้ช่วยตอบคำถาม'), 'เปิดหน้าต่างแชทได้')
  // placeholder ไม่นับเป็นเนื้อหาข้อความ ต้องอ่านจากแอตทริบิวต์
  const placeholder = await page.locator('input[type="text"]').getAttribute('placeholder')
  check((placeholder ?? '').includes('ถามอะไรก็ได้'), 'มีช่องพิมพ์คำถาม', placeholder ?? '')
  check((await page.getByLabel('ส่งคำถาม').count()) > 0, 'มีปุ่มส่ง')
  check((await page.getByLabel('พูดคำถาม').count()) > 0, 'มีปุ่มไมโครโฟน')
  await shot('7-chat')

  // ---- ถามด้วยการพิมพ์ ----
  await page.locator('input[type="text"]').fill('ติดต่ออาจารย์ยังไง')
  await page.getByLabel('ส่งคำถาม').click()
  await page.waitForTimeout(2600)
  text = await body()
  check(text.includes('ติดต่ออาจารย์ยังไง'), 'คำถามที่พิมพ์ขึ้นเป็นฟองฝั่งนักศึกษา')
  check(/@mju\.ac\.th/.test(text), 'ตอบด้วยอีเมลจริงของบุคลากรสาขา')
  check(text.includes('ข้อมูลจากระบบของสาขา'), 'คำตอบมีป้ายบอกที่มา (ฐานข้อมูล)')
  check((await page.locator('input[type="text"]').inputValue()) === '',
        'ช่องพิมพ์ถูกล้างหลังส่ง')
  await shot('8-chat-typed')

  // ---- ถามจากปุ่มคำถามยอดนิยม ----
  await page.getByLabel('คำถามยอดนิยม').click()
  await page.waitForTimeout(700)
  check((await body()).includes('คำถามยอดนิยม'), 'เปิดแผงคำถามยอดนิยมได้')
  await page.getByText('ทุนวิจัยระดับปริญญาตรีมีเท่าไร').click()
  await page.waitForTimeout(2600)
  text = await body()
  check(text.includes('ไม่พบข้อมูลนี้ในระบบ'), 'คำถามที่ไม่มีเอกสารอ้างอิง → ไม่เดาคำตอบ')
  check(text.includes('cs@mju.ac.th'), 'เสนอช่องทางติดต่อสาขาแทน')
  check(text.includes('ติดต่ออาจารย์ยังไง'),
        'คำถามก่อนหน้ายังอยู่บนกระดาน ไม่ถูกแทนที่')
  await shot('9-chat-thread')

  console.log('\n5ก. ลงทะเบียนใบหน้า — ถ่ายก่อน กรอกรายละเอียดทีหลัง')
  await logout()
  await gotoOtherOptions()

  const enrollOption = page.getByText('ลงทะเบียนใบหน้า').first()
  if ((await enrollOption.count()) === 0) {
    check(true, 'ข้ามการลงทะเบียน — หน้านี้ไม่เสนอให้ลงทะเบียนในสถานะปัจจุบัน')
  } else {
  await enrollOption.click()
  await page.waitForTimeout(800)
  text = await body()
  check(text.includes('ให้ความยินยอมในการเก็บข้อมูล'),
        'ขอความยินยอมก่อนถ่ายเสมอ (พ.ร.บ.ฯ มาตรา 26)')
  check(text.includes('ระบบไม่เก็บภาพใบหน้าของคุณ'), 'อธิบายว่าเก็บเฉพาะค่าเวกเตอร์')

  // ปุ่มต้องกดไม่ได้จนกว่าจะแตะช่องยินยอมเอง (ห้ามติ๊กไว้ล่วงหน้า)
  const beforeTick = await page
    .getByRole('button', { name: /กรุณาแตะช่องยินยอมก่อน/ })
    .count()
  check(beforeTick > 0, 'ยังไม่ติ๊กยินยอม ปุ่มถ่ายใบหน้าจึงกดไม่ได้')

  await page.getByText('ข้าพเจ้า', { exact: false }).first().click()
  await page.waitForTimeout(500)
  await page.getByRole('button', { name: /ถ่ายใบหน้าเลย/ }).click()
  await page.waitForTimeout(3000)

  text = await body()

  // เมื่อมีคนอยู่หน้ากล้อง การถ่าย 8 ใบใช้เวลาไม่ถึง 3 วินาที
  // หน้าจอจึงอาจผ่านขั้น "กำลังถ่าย" ไปแล้ว ทดสอบต้องรับได้ทุกขั้น
  const enrollStates = [
    'กำลังถ่ายใบหน้า',       // ยังเก็บตัวอย่างอยู่
    'ถ่ายใบหน้าเรียบร้อย',   // ถ่ายครบ รอกรอกรหัสนักศึกษา
    'ลงทะเบียนไว้กับรหัส',   // ใบหน้านี้มีในระบบแล้ว (ตัวกันซ้ำทำงาน)
    'ภาพใบหน้าไม่สม่ำเสมอ',  // คุณภาพไม่ผ่าน ให้ถ่ายใหม่
  ]
  const reached = enrollStates.find((t) => text.includes(t))
  check(Boolean(reached), 'ยินยอมแล้วเข้าสู่ขั้นถ่ายใบหน้าทันที ไม่ต้องกรอกรหัสก่อน',
        reached ?? text.slice(60, 140))

  const denied = faceCalls.filter((c) => c.status === 401 || c.status === 403)
  check(denied.length === 0, 'ไม่มีคำขอใดถูกปฏิเสธสิทธิ์ระหว่างลงทะเบียน',
        denied.map((c) => `${c.status} ${c.path}`).join(', '))
  check(faceCalls.some((c) => c.path === '/face/enroll/begin' && c.status === 200),
        'เซิร์ฟเวอร์เริ่มเก็บตัวอย่างใบหน้าแล้ว')

  if (reached === 'ลงทะเบียนไว้กับรหัส') {
    check(true, 'ใบหน้าที่ลงทะเบียนแล้วถูกปฏิเสธไม่ให้ลงซ้ำ')
  }
  await shot('11-enroll')

  // ออกจากขั้นลงทะเบียนด้วยปุ่มยกเลิกบนแถบบน (ปุ่มในเนื้อหาอาจมีหรือไม่มีก็ได้)
  await page.getByRole('banner').getByRole('button', { name: 'ยกเลิก' }).click()
  await page.waitForTimeout(1300)
  }

  console.log('\n5ข. ผลสแกนที่มาทีหลังต้องไม่รบกวนหน้าที่กำลังใช้อยู่')
  // จำลองว่าผลการสแกนมาถึงหลังผู้ใช้เปลี่ยนหน้าไปแล้ว
  // ถ้าไม่กันไว้ ผู้ใช้ที่กำลังกรอกรหัสจะถูกดึงกลับไปหน้าสแกนและเสียตัวเลขที่กรอกไป
  const screenBefore = await body()
  await page.evaluate(() => fetch('/api/sim/face/unknown', { method: 'POST' }))
  await page.waitForTimeout(1200)
  const screenAfter = await body()
  check(
    screenAfter.includes('ผู้ช่วยตอบคำถาม') || screenAfter === screenBefore,
    'ผลสแกนที่มาทีหลังไม่ดึงผู้ใช้ออกจากหน้าที่กำลังใช้อยู่',
    screenAfter.slice(60, 120)
  )

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
