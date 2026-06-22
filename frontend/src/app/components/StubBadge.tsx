// A clearly-labelled, non-functional, disabled control. Never a bug — an
// intentional placeholder for a later phase.
export default function StubButton({
  label,
  className = '',
}: {
  label: string
  className?: string
}) {
  return (
    <button
      type="button"
      disabled
      aria-disabled="true"
      title="Coming soon — not yet available"
      className={`flex w-full cursor-not-allowed items-center justify-between gap-2 rounded-lg border border-dashed border-gray-300 bg-gray-50 px-3 py-2 text-left text-sm text-gray-400 ${className}`}
    >
      <span>{label}</span>
      <span className="rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-gray-500">
        coming soon
      </span>
    </button>
  )
}
