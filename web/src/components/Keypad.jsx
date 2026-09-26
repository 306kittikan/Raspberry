import React from 'react'

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'del', '0', 'ok']
const LENGTH = 10

/**
 * แป้นตัวเลขบนจอ สำหรับกรอกรหัสนักศึกษา
 * ช่องแสดงผลปิดบังตัวเลขที่กรอกไปแล้ว เผยเฉพาะตัวล่าสุด
 * เพราะจอตู้มองเห็นได้จากคนที่เดินผ่าน
 */
export default function Keypad({ value, onChange, onSubmit, error }) {
  const press = (key) => {
    if (key === 'del') {
      onChange(value.slice(0, -1))
      return
    }
    if (key === 'ok') {
      onSubmit()
      return
    }
    if (value.length < LENGTH) onChange(value + key)
  }

  return (
    <div>
      <div className="flex justify-center gap-[10px]">
        {Array.from({ length: LENGTH }).map((_, i) => {
          const filled = i < value.length
          const isLast = i === value.length - 1
          return (
            <span
              key={i}
              className={`flex h-[84px] w-[84px] items-center justify-center rounded-[18px] border-2 text-h3 font-bold tabular-nums ${
                filled
                  ? 'border-brand-600 bg-brand-50 text-brand-900'
                  : 'border-brand-100 bg-white text-brand-200'
              }`}
            >
              {filled ? (isLast ? value[i] : '•') : ''}
            </span>
          )
        })}
      </div>

      {error ? (
        <p className="mt-6 text-center text-body font-semibold text-danger-700 animate-fade-in">
          {error}
        </p>
      ) : (
        <p className="mt-6 text-center text-label text-ink-mute">กรอกรหัสนักศึกษา 10 หลัก</p>
      )}

      <div className="mt-8 grid grid-cols-3 gap-5">
        {KEYS.map((key) => {
          if (key === 'del') {
            return (
              <button
                key={key}
                type="button"
                onClick={() => press(key)}
                className="press tap min-h-[150px] rounded-[24px] border-2 border-brand-200 bg-white text-body-lg font-semibold text-brand-800 active:bg-brand-50"
              >
                ลบ
              </button>
            )
          }
          if (key === 'ok') {
            return (
              <button
                key={key}
                type="button"
                onClick={() => press(key)}
                disabled={value.length !== LENGTH}
                className="press tap min-h-[150px] rounded-[24px] border-2 border-brand-700 bg-brand-700 text-body-lg font-bold text-white active:bg-brand-800 disabled:border-brand-100 disabled:bg-brand-100 disabled:text-ink-mute"
              >
                ตกลง
              </button>
            )
          }
          return (
            <button
              key={key}
              type="button"
              onClick={() => press(key)}
              className="press tap min-h-[150px] rounded-[24px] border-2 border-brand-200 bg-white text-h2 font-bold tabular-nums text-brand-900 active:bg-brand-100"
            >
              {key}
            </button>
          )
        })}
      </div>
    </div>
  )
}
