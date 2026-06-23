'use client'

interface Props {
  title: string
  comingIn: string
}

export default function StubCard({ title, comingIn }: Props) {
  return (
    <div className="rounded-xl border-2 border-dashed border-gray-200 bg-gray-50 p-6 text-center">
      <p className="text-base font-semibold text-gray-400">{title}</p>
      <span className="mt-2 inline-block rounded-full bg-gray-200 px-3 py-0.5 text-xs font-medium text-gray-500">
        Coming in {comingIn}
      </span>
    </div>
  )
}
