import React from 'react'
import Stage from './components/Stage'
import DevPanel from './components/DevPanel'
import InactivityOverlay from './components/InactivityOverlay'
import { KioskProvider, useKiosk } from './state/KioskProvider'

import SleepScreen from './screens/SleepScreen'
import IdleScreen from './screens/IdleScreen'
import FaceScanScreen from './screens/FaceScanScreen'
import ConfirmIdentityScreen from './screens/ConfirmIdentityScreen'
import NotRecognizedScreen from './screens/NotRecognizedScreen'
import KeypadScreen from './screens/KeypadScreen'
import ConsentScreen from './screens/ConsentScreen'
import EnrollScreen from './screens/EnrollScreen'
import HomeScreen from './screens/HomeScreen'
import AssistantScreen from './screens/AssistantScreen'
import FaceDataScreen from './screens/FaceDataScreen'

const SCREENS = {
  sleep: SleepScreen,
  idle: IdleScreen,
  scan: FaceScanScreen,
  confirm: ConfirmIdentityScreen,
  unknown: NotRecognizedScreen,
  keypad: KeypadScreen,
  consent: ConsentScreen,
  enroll: EnrollScreen,
  home: HomeScreen,
  assistant: AssistantScreen,
  facedata: FaceDataScreen,
}

/** หน้าที่แสดงข้อมูลส่วนบุคคล ต้องยืนยันตัวตนแล้วเท่านั้น */
const REQUIRE_AUTH = new Set(['home', 'facedata'])

function Router() {
  const { screen, isAuthenticated, logoutCountdown, markActivity } = useKiosk()

  const safeScreen = REQUIRE_AUTH.has(screen) && !isAuthenticated ? 'idle' : screen
  const Screen = SCREENS[safeScreen] || IdleScreen

  // การแตะที่ใดก็ได้นับเป็นการใช้งาน ยกเว้นระหว่างนับถอยหลังออกจากระบบ
  // (ช่วงนั้นต้องกดปุ่ม "ยังใช้งานอยู่" เท่านั้น เพื่อไม่ให้ปัดทิ้งโดยไม่ตั้งใจ)
  const handlePointerDown = () => {
    if (logoutCountdown === null) markActivity()
  }

  return (
    <Stage>
      <div className="h-full w-full" onPointerDown={handlePointerDown}>
        <Screen key={safeScreen} />
      </div>
      <InactivityOverlay />
      <DevPanel />
    </Stage>
  )
}

export default function App() {
  return (
    <KioskProvider>
      <Router />
    </KioskProvider>
  )
}
