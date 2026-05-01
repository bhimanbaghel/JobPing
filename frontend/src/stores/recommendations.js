import { defineStore } from 'pinia'

function authHeaders() {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const useRecommendationsStore = defineStore('recommendations', {
  state: () => ({
    items: [],
    count: 0,
    loading: false,
    error: '',
    code: '',
  }),
  getters: {
    sortedByScore(state) {
      return [...state.items].sort(
        (a, b) => (b.similarity_score || 0) - (a.similarity_score || 0),
      )
    },
  },
  actions: {
    async fetch({ recompute = false } = {}) {
      this.loading = true
      this.error = ''
      this.code = ''
      try {
        const url = recompute
          ? '/api/jobs/recommendations?recompute=1'
          : '/api/jobs/recommendations'
        const res = await fetch(url, { headers: authHeaders() })
        if (res.status === 401) {
          this.error = 'Your session has expired. Please sign in again.'
          this.code = 'unauthorized'
          this.items = []
          this.count = 0
          return
        }
        const data = await res.json().catch(() => ({}))
        if (!res.ok) {
          this.error = data.error || 'Failed to load recommendations.'
          this.code = data.code || ''
          this.items = []
          this.count = 0
          return
        }
        this.items = Array.isArray(data.items) ? data.items : []
        this.count = data.count ?? this.items.length
      } catch (err) {
        this.error = err.message || 'Network error.'
        this.items = []
        this.count = 0
      } finally {
        this.loading = false
      }
    },

    async fetchJob(jobId) {
      const res = await fetch(`/api/jobs/${jobId}`, { headers: authHeaders() })
      if (!res.ok) throw new Error(`Could not load job ${jobId}.`)
      return res.json()
    },
  },
})
