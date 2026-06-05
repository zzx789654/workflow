interface Props {
  className?: string
  rows?: number
}

export function Skeleton({ className = 'h-4 w-full' }: { className?: string }) {
  return <div className={`skeleton ${className}`} />
}

export function CardSkeleton() {
  return (
    <div className="card space-y-3 animate-pulse">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-1/2" />
      <div className="flex gap-2 pt-1">
        <Skeleton className="h-5 w-12 rounded-full" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
    </div>
  )
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 p-3 bg-white rounded-xl border border-gray-100">
          <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-1/4" />
          </div>
          <Skeleton className="h-5 w-16 rounded-full flex-shrink-0" />
        </div>
      ))}
    </div>
  )
}

export function PageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <Skeleton className="h-8 w-48" />
      <div className="grid grid-cols-3 gap-4">
        {[1,2,3].map(i => <Skeleton key={i} className="h-24 rounded-xl" />)}
      </div>
      <div className="space-y-3">
        {[1,2,3,4].map(i => <Skeleton key={i} className="h-16 rounded-xl" />)}
      </div>
    </div>
  )
}
