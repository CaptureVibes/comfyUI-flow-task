import { computed, ref } from 'vue'

/**
 * Investor demo mode toggle.
 *
 * 优先级（高 → 低）：
 *   1. URL query `?investor=1` / `?investor=0` —— 一次性显式开关，也会写入 localStorage 持久化
 *   2. localStorage `investor_mode` —— 之前 URL 设置的值
 *   3. 构建期 env `VITE_INVESTOR_MODE` —— 部署默认
 *   4. 否则 false
 *
 * 投资人模式下：隐藏侧栏 + 顶栏头像；除 /dashboard/formal-backfill 外的
 * 路由均重定向到该页；登录页仍可用。
 */
const STORAGE_KEY = 'investor_mode'

function readInitial() {
  if (typeof window === 'undefined') return false
  const url = new URL(window.location.href)
  const q = url.searchParams.get('investor')
  if (q === '1' || q === 'true') {
    try { localStorage.setItem(STORAGE_KEY, '1') } catch { /* ignore */ }
    return true
  }
  if (q === '0' || q === 'false') {
    try { localStorage.setItem(STORAGE_KEY, '0') } catch { /* ignore */ }
    return false
  }
  let stored = null
  try { stored = localStorage.getItem(STORAGE_KEY) } catch { /* ignore */ }
  if (stored === '1') return true
  if (stored === '0') return false
  return import.meta.env.VITE_INVESTOR_MODE === 'true'
}

const _investorMode = ref(readInitial())

export function useInvestorMode() {
  return {
    isInvestorMode: computed(() => _investorMode.value),
    setInvestorMode(value) {
      _investorMode.value = Boolean(value)
      try { localStorage.setItem(STORAGE_KEY, value ? '1' : '0') } catch { /* ignore */ }
    },
  }
}
