import React, { useState, useEffect } from 'react'
import { api } from '../../api/client'

interface HealthScoreResponse {
  score: number
}

interface Props {
  projectId: string
}

export default function HealthScoreBadge({ projectId }: Props) {
  const [score, setScore] = useState<number | null>(null)

  useEffect(() => {
    api
      .get<HealthScoreResponse>(`/projects/${projectId}/health-score`)
      .then((res) => {
        setScore(res.data.score)
      })
      .catch(() => {
        // silently return null on error
      })
  }, [projectId])

  if (score === null) return null

  let colorClass = 'bg-green-100 text-green-700'
  if (score < 60) colorClass = 'bg-red-100 text-red-700'
  else if (score < 80) colorClass = 'bg-yellow-100 text-yellow-700'

  return (
    <div
      className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 ${colorClass}`}
      title={`健康分數 ${score}`}
    >
      {score}
    </div>
  )
}
