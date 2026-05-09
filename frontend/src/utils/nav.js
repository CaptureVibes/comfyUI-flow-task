import router from '../router'

/**
 * 在新标签页打开应用内的某个路由。
 * target 可以是字符串路径（如 '/dashboard/accounts/123'）或 RouteLocationRaw 对象。
 * 使用 router.resolve(...).href 拿到带 base 的完整路径，避免在子路径部署时丢失前缀。
 */
export function openInNewTab(target) {
  const href = router.resolve(target).href
  window.open(href, '_blank')
}
