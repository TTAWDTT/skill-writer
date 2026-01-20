/**
 * Performance utilities for smoother UX
 */

/**
 * Debounce function - delays execution until after wait milliseconds
 */
export function debounce(fn, wait = 100) {
  let timeout = null
  return function (...args) {
    clearTimeout(timeout)
    timeout = setTimeout(() => fn.apply(this, args), wait)
  }
}

/**
 * Throttle function - ensures function is called at most once per wait milliseconds
 */
export function throttle(fn, wait = 100) {
  let lastTime = 0
  let timeout = null
  return function (...args) {
    const now = Date.now()
    const remaining = wait - (now - lastTime)

    clearTimeout(timeout)

    if (remaining <= 0) {
      lastTime = now
      fn.apply(this, args)
    } else {
      timeout = setTimeout(() => {
        lastTime = Date.now()
        fn.apply(this, args)
      }, remaining)
    }
  }
}

/**
 * RAF-based scroll to bottom - smoother than direct assignment
 */
export function smoothScrollToBottom(element) {
  if (!element) return

  requestAnimationFrame(() => {
    element.scrollTo({
      top: element.scrollHeight,
      behavior: 'smooth'
    })
  })
}

/**
 * Instant scroll to bottom using RAF
 */
export function scrollToBottom(element) {
  if (!element) return

  requestAnimationFrame(() => {
    element.scrollTop = element.scrollHeight
  })
}

/**
 * Memoize function for expensive computations
 */
export function memoize(fn) {
  const cache = new Map()
  return function (...args) {
    const key = JSON.stringify(args)
    if (cache.has(key)) {
      return cache.get(key)
    }
    const result = fn.apply(this, args)
    cache.set(key, result)
    // Limit cache size to prevent memory leaks
    if (cache.size > 100) {
      const firstKey = cache.keys().next().value
      cache.delete(firstKey)
    }
    return result
  }
}
