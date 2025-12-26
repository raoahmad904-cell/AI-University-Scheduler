import axios from 'axios'

const API_BASE = 'http://127.0.0.1:8000'

export async function getStatus() {
  const res = await axios.get(`${API_BASE}/api/status`)
  return res.data
}

export async function login(email: string, password: string) {
  const res = await axios.post(`${API_BASE}/api/login`, { email, password })
  return res.data // {token, role, name, email, sections}
}

export async function allocateExamRooms(
  exam_id: string,
  mode: 'room' | 'department' | 'hybrid' | 'column',
  exam_ids?: string[]
) {
  const res = await axios.post(`${API_BASE}/api/allocate_rooms`, {
    exam_id,
    mode,
    exam_ids,
  })
  return res.data
}

export async function generateExamTimetable(population: number, generations: number) {
  const res = await axios.post(`${API_BASE}/api/generate/exam_timetable`, {
    population,
    generations,
  })
  return res.data
}

export async function generateFullTimetable() {
  const res = await axios.post(`${API_BASE}/api/generate/timetable`)
  return res.data
}

export async function uploadCSV(kind: 'rooms' | 'teachers' | 'courses' | 'students' | 'exams', csv_text: string) {
  const res = await axios.post(`${API_BASE}/api/upload/${kind}`, { csv_text })
  return res.data
}

export async function listExams() {
  const res = await axios.get(`${API_BASE}/api/exams`)
  return res.data as { exams: any[] }
}

// UPDATE: Added optional params to match backend capabilities
export async function fetchStudentTimetable(studentId: string, department?: string, section?: string) {
  // Build query string dynamically
  const params = new URLSearchParams()
  if (department) params.append('department', department)
  if (section) params.append('section', section)
  
  const queryString = params.toString() ? `?${params.toString()}` : ''
  
  const res = await axios.get(`${API_BASE}/api/student/${encodeURIComponent(studentId)}/timetable${queryString}`)
  return res.data
}