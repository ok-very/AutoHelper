interface FeedbackMessageProps {
  message: string
  isError?: boolean
}

export function FeedbackMessage({ message, isError }: FeedbackMessageProps) {
  if (!message) return null
  return (
    <span className={`save-feedback ${isError ? 'save-err' : 'save-ok'}`}>
      {message}
    </span>
  )
}
