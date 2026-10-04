import { useEffect, useId, useRef } from 'react'

const focusable = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export default function Dialog({ title, description, onClose, children, closeLabel = 'Close dialog' }) {
  const dialogRef = useRef(null)
  const previousFocus = useRef(null)
  const onCloseRef = useRef(onClose)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    previousFocus.current = document.activeElement
    const dialog = dialogRef.current
    const first = dialog?.querySelector(focusable)
    first?.focus()

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab' || !dialog) return
      const elements = [...dialog.querySelectorAll(focusable)]
      if (!elements.length) return
      const firstElement = elements[0]
      const lastElement = elements[elements.length - 1]
      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault()
        lastElement.focus()
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault()
        firstElement.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      previousFocus.current?.focus?.()
    }
  }, [])

  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
    <div className="modal" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={description ? descriptionId : undefined}>
      <button type="button" className="modal-close" aria-label={closeLabel} onClick={onClose}>×</button>
      <h2 id={titleId}>{title}</h2>
      {description && <p id={descriptionId} className="muted">{description}</p>}
      {children}
    </div>
  </div>
}
