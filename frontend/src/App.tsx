import { useEffect, useState } from 'react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import * as XLSX from 'xlsx'
import {
  getStatus,
  login as apiLogin,
  allocateExamRooms,
  generateExamTimetable,
  generateFullTimetable,
  uploadCSV,
  listExams,
  fetchStudentTimetable,
} from './api'

type Tab = 'dashboard' | 'exam-rooms' | 'timetables' | 'data'
type Role = 'student' | 'teacher' | 'coordinator'

type TimetableGrid = {
  [day: string]: {
    [slotLabel: string]: string[]
  }
}

function downloadText(filename: string, text: string) {
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function allocationToCSV(roomsResult: any): string {
  const rows = ['room,room_name,capacity,assigned,utilization,dominant_department']
    ; (roomsResult.explanation || []).forEach((r: any) => {
      const utilPct = (r.utilization * 100).toFixed(1)
      rows.push(
        [
          r.room,
          `"${r.room_name || r.room}"`,
          r.capacity,
          r.assigned_count,
          utilPct,
          r.dominant_department || '',
        ].join(',')
      )
    })
  return rows.join('\n')
}

function buildClassGrid(classTT: any, timeslotMap: any, rooms: any, courses: any, teachers: any): TimetableGrid {
  const grid: TimetableGrid = {}
  Object.entries(classTT || {}).forEach(([key, valAny]) => {
    const val = valAny as any
    const [courseId, section] = key.split('|')
    const slotId = val.slot
    const roomId = val.room
    const teacherId = val.teacher
    const slotInfo = timeslotMap[slotId] || { label: slotId }
    const label = slotInfo.label as string
    const [day, time] = label.split(' ')
    const dayKey = day || 'Unknown'
    const timeKey = time ? label : label
    const courseTitle = (courses[courseId]?.title || courseId) as string
    const roomName = (rooms[roomId]?.name || roomId) as string
    const teacherName = (teachers[teacherId]?.name || teacherId) as string
    const entry = `${courseTitle} (Sec ${section}) – ${roomName} – ${teacherName}`
    if (!grid[dayKey]) grid[dayKey] = {}
    if (!grid[dayKey][timeKey]) grid[dayKey][timeKey] = []
    grid[dayKey][timeKey].push(entry)
  })
  return grid
}

function buildLabGrid(labTT: any, timeslotMap: any, rooms: any, courses: any, teachers: any): TimetableGrid {
  const grid: TimetableGrid = {}
  Object.entries(labTT || {}).forEach(([key, valAny]) => {
    const val = valAny as any
    const [courseId, section] = key.split('|')
    const slotIds: string[] = val.slots
    const roomId = val.room
    const teacherId = val.teacher
    const labels = slotIds.map((sid) => (timeslotMap[sid]?.label || sid) as string)
    const first = labels[0] || ''
    const [day] = first.split(' ')
    const dayKey = day || 'Unknown'
    const timeRange = labels.join(', ')
    const courseTitle = (courses[courseId]?.title || courseId) as string
    const roomName = (rooms[roomId]?.name || roomId) as string
    const teacherName = (teachers[teacherId]?.name || teacherId) as string
    const entry = `${courseTitle} (Sec ${section}) – ${roomName} – ${teacherName} – ${timeRange}`
    if (!grid[dayKey]) grid[dayKey] = {}
    if (!grid[dayKey]['Lab']) grid[dayKey]['Lab'] = []
    grid[dayKey]['Lab'].push(entry)
  })
  return grid
}

const sampleTemplates: Record<string, string> = {
  rooms: `id,capacity,type,building,floor,equipment
R101,40,lecture,Main,1,projector
R102,30,lab,CS,2,computers`,
  teachers: `id,name,dept,availability,preferences
T1,Dr. Alice,CS,"MON_9;MON_10;TUE_9","morning"
T2,Prof. Bob,BBA,"MON_9;WED_9;THU_9","morning"`,
  courses: `id,name,dept,sections,credits,lab_required
CS101,Intro to CS,CS,"A;B",3,false
CS101L,Intro to CS Lab,CS,"A",1,true`,
  students: `id,department,section
S001,CS,A
S002,CS,B
S003,BBA,A`,
  exams: `course_id,duration,preferred_window
CS101,2,EXAM_D1_M
BBA201,2,EXAM_D1_E
EE150,3,EXAM_D2_M`,
}

// Guided field definitions for manual entry
const FIELD_DEFS: Record<string, { name: string; label: string; required?: boolean }[]> = {
  exams: [
    { name: 'id', label: 'Exam ID', required: true },
    { name: 'course_code', label: 'Course Code', required: true },
    { name: 'student_id', label: 'Student ID', required: true },
    { name: 'title', label: 'Title' },
    { name: 'department', label: 'Department' },
  ],
  rooms: [
    { name: 'id', label: 'Room ID', required: true },
    { name: 'capacity', label: 'Capacity', required: true },
    { name: 'type', label: 'Type', required: true },
    { name: 'building', label: 'Building' },
    { name: 'floor', label: 'Floor' },
    { name: 'equipment', label: 'Equipment' },
  ],
  teachers: [
    { name: 'id', label: 'Teacher ID', required: true },
    { name: 'name', label: 'Name', required: true },
    { name: 'dept', label: 'Department', required: true },
    { name: 'availability', label: 'Availability (e.g., MON_9;TUE_9)' },
    { name: 'preferences', label: 'Preferences (e.g., morning)' },
  ],
  courses: [
    { name: 'id', label: 'Course ID', required: true },
    { name: 'name', label: 'Name', required: true },
    { name: 'dept', label: 'Department', required: true },
    { name: 'sections', label: 'Sections (e.g., A;B)' },
    { name: 'credits', label: 'Credits' },
    { name: 'lab_required', label: 'Lab Required (true/false)' },
  ],
  students: [
    { name: 'id', label: 'Student ID', required: true },
    { name: 'department', label: 'Department', required: true },
    { name: 'section', label: 'Section', required: true },
  ],
}

export default function App() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<Tab>('dashboard')
  const [status, setStatus] = useState<any>(null)

  // Auth
  const [user, setUser] = useState<{
    role: Role
    token: string
    name: string
    email: string
    sections: string[]
  } | null>(null)
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [authError, setAuthError] = useState<string | null>(null)

  // Student-specific section filter
  const [studentSection, setStudentSection] = useState('') // optional override

  // Student timetable lookup by ID
  const [studentLookupId, setStudentLookupId] = useState('')
  const [studentLookupResult, setStudentLookupResult] = useState<any>(null)
  const [studentLookupError, setStudentLookupError] = useState<string | null>(null)
  const [studentLookupLoading, setStudentLookupLoading] = useState(false)

  // Exam Rooms
  const [examId, setExamId] = useState('')
  const [selectedExamIds, setSelectedExamIds] = useState<string[]>([])
  const [mode, setMode] = useState<'room' | 'department' | 'hybrid' | 'column'>('hybrid')
  const [roomsResult, setRoomsResult] = useState<any>(null)
  const [showRawRooms, setShowRawRooms] = useState(false)
  const [examOptions, setExamOptions] = useState<{ id?: string; exam_id?: string; course_code?: string; title?: string }[]>([])

  // Timetables
  const [examTT, setExamTT] = useState<any>(null)
  const [showRawExamTT, setShowRawExamTT] = useState(false)
  const [fullTT, setFullTT] = useState<any>(null)
  const [classGrid, setClassGrid] = useState<TimetableGrid | null>(null)
  const [labGrid, setLabGrid] = useState<TimetableGrid | null>(null)
  const [showRawFullTT, setShowRawFullTT] = useState(false)

  // Coordinator timetable filters
  const [filterDay, setFilterDay] = useState<string>('all')
  const [filterDept, setFilterDept] = useState<string>('all')
  const [filterSemester, setFilterSemester] = useState<string>('all')
  const [filterSection, setFilterSection] = useState<string>('all')
  const [filterFaculty, setFilterFaculty] = useState<string>('all')
  const [filterType, setFilterType] = useState<'all' | 'class' | 'lab'>('all')
  const [showAIExplanation, setShowAIExplanation] = useState(false)
  const [showConflictDetails, setShowConflictDetails] = useState(false)

  const [classViewMode, setClassViewMode] = useState<'table' | 'calendar'>('table')
  // Exam timetable filters and UI state
  const [examFilterDay, setExamFilterDay] = useState<string>('all')
  const [examFilterSemester, setExamFilterSemester] = useState<string>('all')
  const [examFilterSection, setExamFilterSection] = useState<string>('all')
  const [examFilterDept, setExamFilterDept] = useState<string>('all')
  const [examFilterSlot, setExamFilterSlot] = useState<string>('all')
  const [showExamAIExplanation, setShowExamAIExplanation] = useState(false)
  const [examViewMode, setExamViewMode] = useState<'table' | 'calendar'>('table')

  // Data Upload
  const [dataKind, setDataKind] = useState<'rooms' | 'teachers' | 'courses' | 'students' | 'exams'>('rooms')
  const [csvText, setCsvText] = useState('')
  const [fileName, setFileName] = useState('')
  const [fileText, setFileText] = useState('')
  const [uploadResult, setUploadResult] = useState<any>(null)

  // Manual entry states
  const [formRow, setFormRow] = useState<Record<string, string>>({})
  const [rows, setRows] = useState<Record<string, string>[]>([])

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getStatus()
      .then(setStatus)
      .catch(() => setStatus({ status: 'error', service: 'Backend not reachable' }))
  }, [])

  // Load available exams (respect uploaded data) so we avoid invalid exam IDs.
  useEffect(() => {
    listExams()
      .then((data) => {
        const list = (data.exams || []) as any[]
        setExamOptions(list as any)
        if (list.length) {
          const first = (list[0].id || list[0].exam_id || '').toString()
          const current = (examId || '').toString()
          const hasCurrent = current && list.some((ex) => (ex.id || ex.exam_id || '').toString() === current)
          if (!hasCurrent) setExamId(first)
          if (!selectedExamIds.length) setSelectedExamIds([first])
        }
      })
      .catch(() => { })
  }, [])

  // Reset manual form when dataKind changes
  useEffect(() => {
    setFormRow({})
    setRows([])
    setError(null)
  }, [dataKind])

  const isLoggedIn = !!user
  const role: Role | undefined = user?.role
  const isStudent = role === 'student'
  const isTeacher = role === 'teacher'
  const isCoordinator = role === 'coordinator'
  const isCoordinatorView = isCoordinator || isTeacher

  // Role-based default/allowed tabs
  useEffect(() => {
    if (isTeacher) {
      setActiveTab('timetables')
      return
    }

    // Students should not access coordinator/admin pages
    if (isStudent && (activeTab === 'exam-rooms' || activeTab === 'data')) {
      setActiveTab('dashboard')
    }
  }, [isTeacher, isStudent, activeTab])

  const handleLogin = async () => {
    setAuthError(null)
    setLoading(true)
    try {
      const data = await apiLogin(loginEmail, loginPassword)
      setUser({
        role: data.role,
        token: data.token,
        name: data.name,
        email: data.email,
        sections: data.sections || [],
      })
      setStudentSection((data.sections && data.sections[0]) || '')
      navigate('/')
    } catch (e: any) {
      setAuthError(e?.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    setUser(null)
    setRoomsResult(null)
    setExamTT(null)
    setFullTT(null)
    setUploadResult(null)
    setStudentSection('')
    navigate('/login')
  }

  const formatError = (e: any, fallback: string) => {
    return e?.response?.data?.detail || e?.message || fallback
  }

  const runAllocateRooms = async () => {
    setLoading(true)
    setError(null)
    try {
      const allExamIds = examOptions.map((ex) => (ex.id || ex.exam_id || '').toString()).filter(Boolean)
      const baseExamId = (examId || selectedExamIds[0] || allExamIds[0] || '').toString()
      if (!baseExamId) {
        setError('Select at least one exam to allocate rooms.')
        setLoading(false)
        return
      }
      const columnExamIds = (selectedExamIds.length ? selectedExamIds : baseExamId ? [baseExamId] : allExamIds).filter(Boolean)
      const data = await allocateExamRooms(baseExamId, mode, mode === 'column' ? columnExamIds : undefined)
      setRoomsResult(data)
      setShowRawRooms(false)
    } catch (e: any) {
      setError(formatError(e, 'Error allocating rooms'))
    } finally {
      setLoading(false)
    }
  }

  const runExamGA = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await generateExamTimetable(60, 100)
      setExamTT(data)
      setShowRawExamTT(false)
    } catch (e: any) {
      setError(formatError(e, 'Error generating exam timetable'))
    } finally {
      setLoading(false)
    }
  }

  const runFullTT = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await generateFullTimetable()
      setFullTT(data)
      const { class_timetable, lab_timetable, rooms, teachers, courses, timeslots } = data
      const classG = buildClassGrid(class_timetable, timeslots, rooms, courses, teachers)
      const labG = buildLabGrid(lab_timetable, timeslots, rooms, courses, teachers)
      setClassGrid(classG)
      setLabGrid(labG)
      setShowRawFullTT(false)
    } catch (e: any) {
      setError(formatError(e, 'Error generating full timetable'))
    } finally {
      setLoading(false)
    }
  }

  const handleFileSelect = (file: File | null) => {
    if (!file) return
    setFileName(file.name)

    const lower = file.name.toLowerCase()
    if (lower.endsWith('.xlsx') || lower.endsWith('.xls')) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const data = new Uint8Array(e.target?.result as ArrayBuffer)
        const wb = XLSX.read(data, { type: 'array' })
        const wsName = wb.SheetNames[0]
        const ws = wb.Sheets[wsName]
        const csv = XLSX.utils.sheet_to_csv(ws)
        setFileText('')
        setCsvText(csv)
      }
      reader.readAsArrayBuffer(file)
    } else {
      const reader = new FileReader()
      reader.onload = (e) => {
        const text = e.target?.result as string
        setFileText(text || '')
        setCsvText(text || '')
      }
      reader.readAsText(file)
    }
  }

  const runUpload = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = fileText.trim() ? fileText : csvText
      if (!payload.trim()) {
        setError('Please upload a CSV/Excel file.')
        setLoading(false)
        return
      }
      const data = await uploadCSV(dataKind, payload)
      setUploadResult(data)
      if (dataKind === 'exams') {
        listExams()
          .then((resp) => {
            const list = (resp.exams || []) as any[]
            setExamOptions(list as any)
            if (list.length) {
              const nextId = (list[0].id || list[0].exam_id || examId).toString()
              setExamId(nextId)
              if (!selectedExamIds.length) setSelectedExamIds([nextId])
            }
          })
          .catch(() => { })
      }
    } catch (e: any) {
      setError(e?.message || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  // Manual entry helpers
  const addRow = () => {
    const defs = FIELD_DEFS[dataKind] || []
    for (const d of defs) {
      if (d.required && !(formRow[d.name] || '').trim()) {
        setError(`Missing required field: ${d.label}`)
        return
      }
    }
    setRows((prev) => [...prev, formRow])
    setFormRow({})
    setError(null)
  }

  const removeRow = (idx: number) => {
    setRows((prev) => prev.filter((_, i) => i !== idx))
  }

  const buildCsvFromRows = () => {
    const defs = FIELD_DEFS[dataKind] || []
    const headers = defs.map((d) => d.name)
    const lines = [headers.join(',')]
    rows.forEach((r) => {
      lines.push(headers.map((h) => (r[h] ?? '')).join(','))
    })
    return lines.join('\n')
  }

  const submitRows = async () => {
    if (!rows.length) {
      setError('Add at least one row before uploading.')
      return
    }
    try {
      setLoading(true)
      setError(null)
      const csvTextLocal = buildCsvFromRows()
      const data = await uploadCSV(dataKind, csvTextLocal)
      setUploadResult(data)
    } catch (e: any) {
      setError(e?.message || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  const runStudentLookup = async () => {
    if (!studentLookupId.trim()) {
      setStudentLookupError('Enter a student ID')
      return
    }
    try {
      setStudentLookupLoading(true)
      setStudentLookupError(null)
      const data = await fetchStudentTimetable(studentLookupId.trim())
      setStudentLookupResult(data)
      const derivedSection = (data.student?.section || '').toString()
      if (derivedSection) {
        setStudentSection(derivedSection)
      }
    } catch (e: any) {
      setStudentLookupResult(null)
      setStudentLookupError(formatError(e, 'Lookup failed'))
    } finally {
      setStudentLookupLoading(false)
    }
  }

  // Filter class grid for student view using their sections (from login) or override
  const filteredClassGrid: TimetableGrid | null = (() => {
    if (!classGrid) return null
    if (!isStudent) return classGrid

    const rawTargets = (user?.sections || []).map((s) => s.toLowerCase())
    if (studentSection.trim()) rawTargets.push(studentSection.trim().toLowerCase())
    if (!rawTargets.length) return {}

    // Build a richer set of tokens: full course|section and section-only (sec A)
    const targetTokens: string[] = []
    rawTargets.forEach((t) => {
      targetTokens.push(t)
      const parts = t.split('|')
      if (parts.length > 1) {
        const sectionPart = parts[1]
        if (sectionPart) {
          targetTokens.push(`sec ${sectionPart}`)
          targetTokens.push(sectionPart)
        }
      }
    })

    const filtered: TimetableGrid = {}
    Object.entries(classGrid).forEach(([day, slots]) => {
      Object.entries(slots).forEach(([timeKey, entries]) => {
        const kept = entries.filter((entry) => {
          const el = entry.toLowerCase()
          return targetTokens.some((tok) => el.includes(tok))
        })
        if (kept.length) {
          if (!filtered[day]) filtered[day] = {}
          filtered[day][timeKey] = kept
        }
      })
    })
    return filtered
  })()

  // Extract unique filter options from fullTT data (for coordinator view)
  const filterOptions = ((): {
    days: string[]
    departments: string[]
    semesters: string[]
    sections: string[]
    faculties: string[]
  } => {
    if (!fullTT) return { days: [], departments: [], sections: [], faculties: [], semesters: [] }
    const days = new Set<string>()
    const departments = new Set<string>()
    const semesters = new Set<string>()
    const sections = new Set<string>()
    const faculties = new Set<string>()

    // Extract from class_timetable
    Object.entries(fullTT.class_timetable || {}).forEach(([key, val]: [string, any]) => {
      const [courseId, section] = key.split('|')
      sections.add(section || 'N/A')
      // Get department from course
      const course = fullTT.courses?.[courseId]
      if (course?.dept || course?.department) {
        departments.add(course.dept || course.department)
      }
      if (course?.semester) {
        semesters.add(course.semester.toString())
      }
      // Get teacher name
      const teacher = fullTT.teachers?.[val.teacher]
      if (teacher?.name) faculties.add(teacher.name)
      // Get day from slot
      const slot = fullTT.timeslots?.[val.slot]
      if (slot?.label) {
        const dayPart = slot.label.split(' ')[0]
        days.add(dayPart)
      }
    })

    // Extract from lab_timetable
    Object.entries(fullTT.lab_timetable || {}).forEach(([key, val]: [string, any]) => {
      const [courseId, section] = key.split('|')
      sections.add(section || 'N/A')
      const course = fullTT.courses?.[courseId]
      if (course?.dept || course?.department) {
        departments.add(course.dept || course.department)
      }
      if (course?.semester) {
        semesters.add(course.semester.toString())
      }
      const teacher = fullTT.teachers?.[val.teacher]
      if (teacher?.name) faculties.add(teacher.name)
      if (val.slots?.[0]) {
        const slot = fullTT.timeslots?.[val.slots[0]]
        if (slot?.label) {
          const dayPart = slot.label.split(' ')[0]
          days.add(dayPart)
        }
      }
    })

    return {
      days: Array.from(days).sort(),
      departments: Array.from(departments).sort(),
      semesters: Array.from(semesters).sort((a, b) => a.localeCompare(b, undefined, { numeric: true })),
      sections: Array.from(sections).sort(),
      faculties: Array.from(faculties).sort(),
    }
  })()

  // Compute constraint validation metrics
  const constraintMetrics = (() => {
    if (!fullTT) return null
    const roomConflicts: string[] = []
    const facultyConflicts: string[] = []
    const sectionConflicts: string[] = []
    const facultyOverload: string[] = []

    // Track room-slot usage
    const roomSlotUsage: Record<string, string[]> = {}
    // Track teacher-slot usage
    const teacherSlotUsage: Record<string, string[]> = {}
    // Track section-slot usage (section group per day/slot)
    // Key should be: dept|program|semester|section|slot to match backend logic
    const sectionSlotUsage: Record<string, string[]> = {}
    // Track teacher day counts
    const teacherDayCounts: Record<string, Record<string, number>> = {}

    // Helper to extract program and semester from course ID
    // Course IDs like CSBS01T01, CSMS08L02 => program=BS/MS/PHD, semester=01/08
    const inferProgramSemester = (courseId: string, course: any): { program: string; semester: string } => {
      let program = course?.program || ''
      let semester = course?.semester?.toString() || ''

      if (!program || !semester) {
        const cid = (courseId || '').toUpperCase()
        // Extract program
        if (!program) {
          if (cid.includes('PHD')) program = 'PHD'
          else if (cid.includes('MS')) program = 'MS'
          else if (cid.includes('BS')) program = 'BS'
          else program = 'BS' // default
        }
        // Extract semester (first 2 consecutive digits)
        if (!semester) {
          for (let i = 0; i < cid.length - 1; i++) {
            if (/\d/.test(cid[i]) && /\d/.test(cid[i + 1])) {
              semester = cid[i] + cid[i + 1]
              break
            }
          }
          if (!semester) semester = '01'
        }
      }
      return { program, semester }
    }

    // Process classes
    Object.entries(fullTT.class_timetable || {}).forEach(([key, val]: [string, any]) => {
      const [courseId, section] = key.split('|')
      const roomId = val.room
      const slotId = val.slot
      const teacherId = val.teacher
      const teacherName = fullTT.teachers?.[teacherId]?.name || teacherId
      const roomName = fullTT.rooms?.[roomId]?.name || roomId
      const course = fullTT.courses?.[courseId]
      const dept = course?.dept || course?.department || 'N/A'
      const { program, semester } = inferProgramSemester(courseId, course)
      const slotLabel = fullTT.timeslots?.[slotId]?.label || slotId
      const day = slotLabel.split(' ')[0]

      // Check room conflicts
      const roomKey = `${roomId}|${slotId}`
      if (!roomSlotUsage[roomKey]) roomSlotUsage[roomKey] = []
      roomSlotUsage[roomKey].push(`${key} (${roomName} @ ${slotLabel})`)

      // Check teacher conflicts
      const teacherKey = `${teacherId}|${slotId}`
      if (!teacherSlotUsage[teacherKey]) teacherSlotUsage[teacherKey] = []
      teacherSlotUsage[teacherKey].push(`${key} (${teacherName} @ ${slotLabel})`)

      // Check section conflicts (same dept+program+semester+section same time)
      // This matches the backend CSP logic that groups students by dept|program|semester|section
      const sectionKey = `${dept}|${program}|${semester}|${section}|${slotId}`
      if (!sectionSlotUsage[sectionKey]) sectionSlotUsage[sectionKey] = []
      sectionSlotUsage[sectionKey].push(`${key} @ ${slotLabel}`)

      // Track teacher daily load
      if (!teacherDayCounts[teacherId]) teacherDayCounts[teacherId] = {}
      teacherDayCounts[teacherId][day] = (teacherDayCounts[teacherId][day] || 0) + 1
    })

    // Process labs
    Object.entries(fullTT.lab_timetable || {}).forEach(([key, val]: [string, any]) => {
      const [courseId, section] = key.split('|')
      const roomId = val.room
      const teacherId = val.teacher
      const teacherName = fullTT.teachers?.[teacherId]?.name || teacherId
      const roomName = fullTT.rooms?.[roomId]?.name || roomId
      const course = fullTT.courses?.[courseId]
      const dept = course?.dept || course?.department || 'N/A'
      const { program, semester } = inferProgramSemester(courseId, course)

      // A lab often spans multiple consecutive slots; for daily load, count it once per day
      const labDays = new Set<string>()

      for (const slotId of val.slots || []) {
        const slotLabel = fullTT.timeslots?.[slotId]?.label || slotId
        const day = slotLabel.split(' ')[0]
        labDays.add(day)

        // Check room conflicts
        const roomKey = `${roomId}|${slotId}`
        if (!roomSlotUsage[roomKey]) roomSlotUsage[roomKey] = []
        roomSlotUsage[roomKey].push(`${key} LAB (${roomName} @ ${slotLabel})`)

        // Check teacher conflicts
        const teacherKey = `${teacherId}|${slotId}`
        if (!teacherSlotUsage[teacherKey]) teacherSlotUsage[teacherKey] = []
        teacherSlotUsage[teacherKey].push(`${key} LAB (${teacherName} @ ${slotLabel})`)

        // Check section conflicts (same dept+program+semester+section same time)
        const sectionKey = `${dept}|${program}|${semester}|${section}|${slotId}`
        if (!sectionSlotUsage[sectionKey]) sectionSlotUsage[sectionKey] = []
        sectionSlotUsage[sectionKey].push(`${key} LAB @ ${slotLabel}`)

        // Track teacher daily load
      }

      // Apply daily load increment once per lab per day (not per slot)
      if (!teacherDayCounts[teacherId]) teacherDayCounts[teacherId] = {}
      for (const day of labDays) {
        teacherDayCounts[teacherId][day] = (teacherDayCounts[teacherId][day] || 0) + 1
      }
    })

    // Count conflicts
    Object.entries(roomSlotUsage).forEach(([, entries]) => {
      if (entries.length > 1) roomConflicts.push(entries.join(' vs '))
    })
    Object.entries(teacherSlotUsage).forEach(([, entries]) => {
      if (entries.length > 1) facultyConflicts.push(entries.join(' vs '))
    })
    Object.entries(sectionSlotUsage).forEach(([, entries]) => {
      if (entries.length > 1) sectionConflicts.push(entries.join(' vs '))
    })

    // Check faculty overload (>4 classes per day is soft warning)
    Object.entries(teacherDayCounts).forEach(([teacherId, dayCounts]) => {
      const teacherName = fullTT.teachers?.[teacherId]?.name || teacherId
      Object.entries(dayCounts).forEach(([day, count]) => {
        if (count > 4) {
          facultyOverload.push(`${teacherName}: ${count} classes on ${day}`)
        }
      })
    })

    return {
      roomConflicts: roomConflicts.length,
      roomConflictDetails: roomConflicts,
      facultyConflicts: facultyConflicts.length,
      facultyConflictDetails: facultyConflicts,
      sectionConflicts: sectionConflicts.length,
      sectionConflictDetails: sectionConflicts,
      facultyOverload: facultyOverload.length,
      facultyOverloadDetails: facultyOverload,
    }
  })()

  // Apply coordinator filters to classGrid and labGrid
  const coordFilteredClassGrid: TimetableGrid | null = (() => {
    if (!classGrid || !fullTT || !isCoordinatorView) return classGrid
    if (filterDay === 'all' && filterDept === 'all' && filterSemester === 'all' && filterSection === 'all' && filterFaculty === 'all') {
      return classGrid
    }

    const filtered: TimetableGrid = {}
    Object.entries(classGrid).forEach(([day, slots]) => {
      // Filter by day
      if (filterDay !== 'all' && day !== filterDay) return

      Object.entries(slots).forEach(([timeKey, entries]) => {
        const kept = entries.filter((entry) => {
          // Entry format: "CourseTitle (Sec X) – RoomName – TeacherName"

          // 1. Basic string filters (Section & Faculty)
          if (filterSection !== 'all') {
            const secMatch = entry.match(/\(Sec\s+(\w+)\)/)
            if (!secMatch || secMatch[1] !== filterSection) return false
          }
          if (filterFaculty !== 'all') {
            if (!entry.includes(filterFaculty)) return false
          }

          // 2. Metadata filters (Department & Semester)
          // We only need to lookup the course if these filters are active
          if (filterDept !== 'all' || filterSemester !== 'all') {
            const courseIdentifier = entry.split(' (Sec ')[0]

            // IMPROVED LOOKUP: Check Title, ID, and Course_ID
            const matchingCourse = Object.values(fullTT.courses || {}).find(
              (c: any) => c.title === courseIdentifier || c.id === courseIdentifier || c.course_id === courseIdentifier
            ) as any

            // STRICT CHECK: If we can't find the course data, we can't verify Dept/Sem, so we exclude it.
            if (!matchingCourse) return false

            // Department filter
            if (filterDept !== 'all') {
              const dept = matchingCourse.dept || matchingCourse.department
              if (dept !== filterDept) return false
            }

            // Semester filter
            if (filterSemester !== 'all') {
              const sem = matchingCourse.semester?.toString()
              if (sem !== filterSemester) return false
            }
          }
          return true
        })

        if (kept.length) {
          if (!filtered[day]) filtered[day] = {}
          filtered[day][timeKey] = kept
        }
      })
    })
    return filtered
  })()

  const coordFilteredLabGrid: TimetableGrid | null = (() => {
    if (!labGrid || !fullTT || !isCoordinatorView) return labGrid
    if (filterDay === 'all' && filterDept === 'all' && filterSemester === 'all' && filterSection === 'all' && filterFaculty === 'all') {
      return labGrid
    }

    const filtered: TimetableGrid = {}
    Object.entries(labGrid).forEach(([day, slots]) => {
      if (filterDay !== 'all' && day !== filterDay) return

      Object.entries(slots).forEach(([slotKey, entries]) => {
        const kept = entries.filter((entry) => {
          // 1. Basic string filters
          if (filterSection !== 'all') {
            const secMatch = entry.match(/\(Sec\s+(\w+)\)/)
            if (!secMatch || secMatch[1] !== filterSection) return false
          }
          if (filterFaculty !== 'all') {
            if (!entry.includes(filterFaculty)) return false
          }

          // 2. Metadata filters (Department & Semester)
          if (filterDept !== 'all' || filterSemester !== 'all') {
            const courseIdentifier = entry.split(' (Sec ')[0]

            // IMPROVED LOOKUP
            const matchingCourse = Object.values(fullTT.courses || {}).find(
              (c: any) => c.title === courseIdentifier || c.id === courseIdentifier || c.course_id === courseIdentifier
            ) as any

            // STRICT CHECK
            if (!matchingCourse) return false

            if (filterDept !== 'all') {
              const dept = matchingCourse.dept || matchingCourse.department
              if (dept !== filterDept) return false
            }

            if (filterSemester !== 'all') {
              const sem = matchingCourse.semester?.toString()
              if (sem !== filterSemester) return false
            }
          }
          return true
        })

        if (kept.length) {
          if (!filtered[day]) filtered[day] = {}
          filtered[day][slotKey] = kept
        }
      })
    })
    return filtered
  })()

  // ---------- RENDER SECTIONS ----------

  const renderLoginBar = () => {
    if (!isLoggedIn) return null
    return (
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="login-row">
          <div>
            <div className="stat-label">Logged in as</div>
            <div className="stat-value">{user?.name}</div>
            <div className="stat-sub">
              {user?.email} · {user?.role}
            </div>

          </div>
          <button className="btn-secondary" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>
    )
  }

  const renderDashboard = () => (
    <div>
      {renderLoginBar()}
      <h2 className="section-title">Dashboard</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Backend Status</div>
          <div className="stat-value" style={{ color: status?.status === 'ok' ? '#10b981' : '#ef4444' }}>
            {status?.status || 'Loading...'}
          </div>
          <div className="stat-sub">{status?.service || ''}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Service</div>
          <div className="stat-value">AI Scheduler</div>
          <div className="stat-sub">Timetabling & Room Allocation</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Algorithms</div>
          <div className="stat-value">CSP + GA + Heuristics</div>
          <div className="stat-sub">Constraint Satisfaction & Genetic & Greedy Approach</div>
        </div>
      </div>
    </div>
  )

  const renderExamRooms = () => (
    <div>
      <h2 className="section-title">🏟️ Exam Room Allocation</h2>
      {renderLoginBar()}

      {!(isCoordinator || isTeacher || isStudent) && <p className="help-text">Please log in.</p>}

      {isCoordinator && (
        <div className="card card-glow">
          <div className="card-header">
            <div>
              <h3 className="card-title">⚙️ Configuration</h3>
              <p className="help-text" style={{ margin: 0 }}>
                Choose an exam and allocation mode, then generate a room plan.
              </p>
            </div>
            <div className="actions">
              <span className="badge" title="Current allocation mode">
                {mode === 'room' ? '🏫' : mode === 'department' ? '🏛️' : mode === 'hybrid' ? '🧩' : '🧱'} {mode}
              </span>
            </div>
          </div>

          <div className="config-grid">
            <div className="form-row">
              <label>Exam:</label>
              {examOptions.length ? (
                <select
                  value={examId}
                  onChange={(e) => {
                    const val = e.target.value
                    setExamId(val)
                    if (mode !== 'column') setSelectedExamIds([val])
                  }}
                  className="input"
                >
                  {examOptions.map((ex) => {
                    const val = (ex.id || ex.exam_id || '').toString()
                    const title = (ex.title || '').toString().trim()
                    const shortTitle = title.length > 38 ? `${title.slice(0, 35)}…` : title
                    const label = `${val} • ${(ex.course_code || '').toString().trim()} ${shortTitle}`.trim()
                    return (
                      <option key={val} value={val} title={`${val} • ${(ex.course_code || '').toString().trim()} ${title}`.trim()}>
                        {label}
                      </option>
                    )
                  })}
                </select>
              ) : (
                <input value={examId} onChange={(e) => setExamId(e.target.value)} className="input" />
              )}
            </div>

            <div className="form-row">
              <label>Mode:</label>
              <select value={mode} onChange={(e) => setMode(e.target.value as any)} className="input">
                <option value="room">🏫 Room-based</option>
                <option value="department">🏛️ Department-based</option>
                <option value="hybrid">🧩 Hybrid</option>
                <option value="column">🧱 Column mix (multi-exam)</option>
              </select>
            </div>
          </div>

          {mode === 'column' && (
            <div className="form-row">
              <label>Select exams (multi):</label>
              <div className="field-stack">
                <select
                  multiple
                  value={selectedExamIds}
                  onChange={(e) => {
                    const vals = Array.from(e.target.selectedOptions).map((o) => o.value)
                    setSelectedExamIds(vals)
                    if (!examId && vals.length) setExamId(vals[0])
                  }}
                  className="input input-multi"
                >
                  {examOptions.map((ex) => {
                    const val = (ex.id || ex.exam_id || '').toString()
                    const title = (ex.title || '').toString().trim()
                    const shortTitle = title.length > 38 ? `${title.slice(0, 35)}…` : title
                    const label = `${val} • ${(ex.course_code || '').toString().trim()} ${shortTitle}`.trim()
                    return (
                      <option key={val} value={val} title={`${val} • ${(ex.course_code || '').toString().trim()} ${title}`.trim()}>
                        {label}
                      </option>
                    )
                  })}
                </select>
                <div className="help-text" style={{ margin: 0 }}>
                  Tip: In column mode you can allocate multiple exams together; each column stays single-exam.
                </div>
              </div>
            </div>
          )}

          <div className="config-actions">
            <button onClick={runAllocateRooms} className="btn-primary" disabled={loading}>
              {loading ? 'Allocating...' : '🎯 Allocate Rooms'}
            </button>
          </div>
        </div>
      )}

      {isTeacher && !isCoordinator && <p className="help-text">Teacher view: read-only allocation (no generate).</p>}
      {isStudent && <p className="help-text">Student view: read-only allocation.</p>}

      {error && <div className="error-box">{error}</div>}

      {roomsResult && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">📌 Allocation Summary</h3>
            {isCoordinator && (
              <div className="actions">
                <button
                  className="btn-secondary"
                  onClick={() => downloadText('exam_room_allocation.json', JSON.stringify(roomsResult, null, 2))}
                >
                  ⬇️ Export JSON
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => downloadText('exam_room_allocation.csv', allocationToCSV(roomsResult))}
                >
                  ⬇️ Export CSV
                </button>
              </div>
            )}
          </div>

          {(() => {
            const roomRows = Array.isArray(roomsResult.explanation) ? roomsResult.explanation : []
            const roomsCount = roomRows.length
            const totalCapacity = roomRows.reduce((sum: number, r: any) => sum + (Number(r.capacity) || 0), 0)
            const totalAssigned = roomRows.reduce((sum: number, r: any) => sum + (Number(r.assigned_count) || 0), 0)
            const avgUtil = roomsCount
              ? roomRows.reduce((sum: number, r: any) => sum + (Number(r.utilization) || 0), 0) / roomsCount
              : 0
            const unassigned = (roomsResult as any)?.allocation?._unassigned
            const unassignedCount = Array.isArray(unassigned)
              ? unassigned.length
              : unassigned && typeof unassigned === 'object'
                ? Object.keys(unassigned).length
                : 0

            return (
              <div className="stats-grid" style={{ marginTop: 0, marginBottom: 8 }}>
                <div className="stat-card">
                  <div className="stat-label">🧪 Exam</div>
                  <div className="stat-value" style={{ fontSize: 18 }}>{roomsResult.exam_id || '-'}</div>
                  <div className="stat-sub">Selected exam</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">🧭 Mode</div>
                  <div className="stat-value" style={{ fontSize: 18 }}>{roomsResult.mode || '-'}</div>
                  <div className="stat-sub">Allocation strategy</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">🏟️ Rooms</div>
                  <div className="stat-value">{roomsCount}</div>
                  <div className="stat-sub">Total capacity: {totalCapacity}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">👥 Assigned</div>
                  <div className="stat-value">{totalAssigned}</div>
                  <div className="stat-sub">
                    Avg utilization: {(avgUtil * 100).toFixed(0)}% · Unassigned: {unassignedCount}
                  </div>
                </div>
              </div>
            )
          })()}

          <div className="info-row">
            <span className="info-label">Mode:</span>
            <span className="info-value">{roomsResult.mode}</span>
          </div>
          <div className="info-row">
            <span className="info-label">Exam:</span>
            <span className="info-value">{roomsResult.exam_id}</span>
          </div>
          <h4 className="subhead">🏛️ Room Details</h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>🏫 Room</th>
                <th>🪑 Capacity</th>
                <th>👥 Assigned</th>
                <th>📈 Utilization</th>
                <th>🏷️ Dominant Dept</th>
                <th>✅ Status</th>
              </tr>
            </thead>
            <tbody>
              {roomsResult.explanation?.map((row: any) => (
                <tr key={row.room}>
                  <td>{row.room_name || row.room}</td>
                  <td>{row.capacity}</td>
                  <td>{row.assigned_count}</td>
                  <td>
                    <span className="badge">{(row.utilization * 100).toFixed(1)}%</span>
                  </td>
                  <td>{row.dominant_department || '-'}</td>
                  <td>
                    <span className={row.is_mixed_departments ? 'badge badge-warn' : 'badge badge-ok'}>
                      {row.comment}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <h4 className="subhead">📊 Room Utilization</h4>
          <div className="heatmap-grid">
            {Object.entries(roomsResult.room_utilization_heatmap || {}).map(([roomId, util]) => (
              <div key={roomId} className="heatmap-item">
                <div className="heatmap-label">{roomId}</div>
                <div className="heatmap-bar-container">
                  <div className="heatmap-bar" style={{ width: `${(util as number) * 100}%` }} />
                </div>
                <div className="heatmap-value">{((util as number) * 100).toFixed(0)}%</div>
              </div>
            ))}
          </div>

          {roomsResult.mode === 'column' && (
            <div style={{ marginTop: 16 }}>
              <h4 className="subhead">🪑 Column Seating (max one exam per row across columns)</h4>
              {Object.entries(roomsResult.allocation || {})
                .filter(([roomId]) => roomId !== '_unassigned')
                .map(([roomId, payload]: any) => {
                  const rows = payload?.rows || []
                  const columns = payload?.columns || 0
                  return (
                    <div key={roomId} className="card" style={{ marginTop: 8, padding: 12 }}>
                      <div className="info-row">
                        <span className="info-label">Room:</span>
                        <span className="info-value">{roomId}</span>
                      </div>
                      <div className="info-row">
                        <span className="info-label">Grid:</span>
                        <span className="info-value">{columns} columns × {payload?.seats_per_column || 0} seats</span>
                      </div>
                      <div className="info-row">
                        <span className="info-label">Rows filled:</span>
                        <span className="info-value">{rows.length}</span>
                      </div>
                      {rows.length > 0 && (
                        <div className="small-grid">
                          {rows.slice(0, 3).map((row: any, idx: number) => (
                            <div key={idx} style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                              <span className="info-label">Row {idx + 1}:</span>
                              {row.map((seat: any) => (
                                <span key={seat.column} className="badge">
                                  {seat.column}: {seat.exam_id}
                                </span>
                              ))}
                            </div>
                          ))}
                          {rows.length > 3 && <div className="help-text">Showing first 3 rows only.</div>}
                        </div>
                      )}
                    </div>
                  )
                })}

              {roomsResult.allocation && roomsResult.allocation._unassigned && (
                <div className="error-box" style={{ marginTop: 12 }}>
                  Unassigned students (capacity short):
                  <pre className="code-block">{JSON.stringify(roomsResult.allocation._unassigned, null, 2)}</pre>
                </div>
              )}
            </div>
          )}

          {isCoordinator && (
            <>
              <button className="btn-link" onClick={() => setShowRawRooms(!showRawRooms)} style={{ marginTop: 12 }}>
                {showRawRooms ? 'Hide' : 'Show'} Raw JSON
              </button>
              {showRawRooms && (
                <pre className="code-block" style={{ marginTop: 8 }}>
                  {JSON.stringify(roomsResult, null, 2)}
                </pre>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )

  const renderTimetables = () => (
    <div>
      <h2 className="section-title">Timetables</h2>
      {renderLoginBar()}

      {!isLoggedIn && <p className="help-text">Please log in.</p>}

      {isCoordinator && (
        <div className="card">
          <h3 className="card-title">Generate Timetables</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={runExamGA} className="btn-primary" disabled={loading}>
              {loading ? 'Generating...' : 'Exam Timetable (GA)'}
            </button>
            <button onClick={runFullTT} className="btn-primary" disabled={loading}>
              {loading ? 'Generating...' : 'Class + Lab Timetable'}
            </button>
          </div>
        </div>
      )}
      {isTeacher && !isCoordinator && (
        <div className="card">
          <h3 className="card-title">Class & Lab Timetable</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={runFullTT} className="btn-primary" disabled={loading}>
              {loading ? 'Loading...' : 'Class + Lab Timetable'}
            </button>
          </div>
        </div>
      )}
      {isStudent && !isCoordinator && (
        <div className="card">
          <h3 className="card-title">View Timetables</h3>
          <p className="help-text">Generation allowed for coordinator only.</p>
        </div>
      )}

      {error && <div className="error-box">{error}</div>}

      {isStudent && (
        <div className="card card-glow">
          <div className="card-header">
            <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="title-icon">🎓</span>
              Student Timetable Lookup
            </h3>
          </div>

          <p className="help-text" style={{ marginTop: 0 }}>
            Enter a student ID (from students.csv) to fetch that student&apos;s classes + labs with teacher, room, and time.
          </p>

          <div className="config-grid" style={{ marginTop: 8 }}>
            <div className="field-stack">
              <div className="field-label">🆔 Student ID</div>
              <input
                className="input"
                value={studentLookupId}
                onChange={(e) => setStudentLookupId(e.target.value)}
                placeholder="e.g., S_EE_BS_03A013"
                inputMode="text"
                autoComplete="off"
              />
              <div className="help-text" style={{ margin: 0 }}>
                Tip: copy an ID from uploads/students.csv
              </div>
            </div>
            <div className="field-stack" style={{ justifyContent: 'flex-end' }}>
              <div className="field-label" style={{ opacity: 0 }}>
                Action
              </div>
              <div className="lookup-actions">
                <button onClick={runStudentLookup} className="btn-primary" disabled={studentLookupLoading}>
                  {studentLookupLoading ? '⏳ Fetching…' : '🔎 Fetch timetable'}
                </button>
              </div>
            </div>
          </div>

          {studentLookupError && <div className="error-box">{studentLookupError}</div>}

          {studentLookupResult && (
            <div style={{ marginTop: 12 }}>
              <div className="student-meta-grid">
                <div className="meta-card">
                  <div className="meta-label">🎓 Student</div>
                  <div className="meta-value">{studentLookupResult.student?.id || 'N/A'}</div>
                </div>
                <div className="meta-card">
                  <div className="meta-label">🏛️ Department</div>
                  <div className="meta-value">{studentLookupResult.student?.department || 'N/A'}</div>
                </div>
                <div className="meta-card">
                  <div className="meta-label">🧩 Section</div>
                  <div className="meta-value">{studentLookupResult.student?.section || 'N/A'}</div>
                </div>
              </div>

              {(() => {
                const combined = [
                  ...(studentLookupResult.classes || []),
                  ...(studentLookupResult.labs || []),
                ]
                return (
                  <>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: 14 }}>
                      <h4 className="subhead" style={{ margin: 0 }}>
                        <span className="subhead-icon">📚</span>
                        Classes & Labs
                        <span className="exam-count-badge" style={{ marginLeft: 10 }}>{combined.length}</span>
                      </h4>
                    </div>

                    {!combined.length ? (
                      <div className="empty-state" style={{ marginTop: 10 }}>
                        <div className="empty-state-icon">🗓️</div>
                        <div className="empty-state-title">No timetable entries found</div>
                        <div className="empty-state-text">Check the Student ID and try again.</div>
                      </div>
                    ) : (
                      <table className="data-table" style={{ marginTop: 10 }}>
                        <thead>
                          <tr>
                            <th>📘 Course</th>
                            <th>🧩 Section</th>
                            <th>⏰ Timeslot</th>
                            <th>🏫 Room</th>
                            <th>🧑‍🏫 Teacher</th>
                            <th>🏷️ Type</th>
                          </tr>
                        </thead>
                        <tbody>
                          {combined.map((row: any, idx: number) => (
                            <tr key={idx}>
                              <td>{row.course_title || row.course_id}</td>
                              <td>{row.section}</td>
                              <td>
                                {row.type === 'lab'
                                  ? (row.timeslot_labels || []).join(', ')
                                  : row.timeslot_label}
                              </td>
                              <td>{row.room_name || row.room_id}</td>
                              <td>{row.teacher_name || row.teacher_id}</td>
                              <td>
                                {row.type === 'lab' ? (
                                  <span className="badge badge-warn type-pill">🧪 Lab</span>
                                ) : (
                                  <span className="badge badge-ok type-pill">📚 Class</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </>
                )
              })()}
            </div>
          )}
        </div>
      )}

      {examTT && (
        <div className="card exam-timetable-card">
          <div className="card-header">
            <h3 className="card-title">
              <span className="title-icon">📝</span>
              Exam Timetable (Genetic Algorithm)
            </h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {isCoordinator && (
                <>
                  <button
                    className={`btn-view-mode ${examViewMode === 'table' ? 'active' : ''}`}
                    onClick={() => setExamViewMode('table')}
                    title="Table View"
                  >
                    📋
                  </button>
                  <button
                    className={`btn-view-mode ${examViewMode === 'calendar' ? 'active' : ''}`}
                    onClick={() => setExamViewMode('calendar')}
                    title="Calendar View"
                  >
                    📅
                  </button>
                  <button
                    className="btn-secondary"
                    onClick={() => downloadText('exam_timetable_ga.json', JSON.stringify(examTT, null, 2))}
                  >
                    📥 Export JSON
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Exam Constraint Summary Bar */}
          <div className="exam-constraint-summary-bar">
            <div className={`exam-constraint-item ${(examTT.metrics?.student_conflicts || 0) === 0 ? 'success' : 'error'}`}>
              <span className="constraint-icon">{(examTT.metrics?.student_conflicts || 0) === 0 ? '✔' : '✖'}</span>
              <span className="constraint-label">Student Conflicts:</span>
              <span className="constraint-value">{examTT.metrics?.student_conflicts || 0}</span>
            </div>
            <div className={`exam-constraint-item ${(examTT.metrics?.room_conflicts || 0) === 0 ? 'success' : 'error'}`}>
              <span className="constraint-icon">{(examTT.metrics?.room_conflicts || 0) === 0 ? '✔' : '✖'}</span>
              <span className="constraint-label">Room Conflicts:</span>
              <span className="constraint-value">{examTT.metrics?.room_conflicts || 0}</span>
            </div>
            <div className={`exam-constraint-item ${(examTT.metrics?.student_same_day_conflicts || 0) === 0 ? 'success' : 'warning'}`}>
              <span className="constraint-icon">{(examTT.metrics?.student_same_day_conflicts || 0) === 0 ? '✔' : '⚠'}</span>
              <span className="constraint-label">Same-Day Exams:</span>
              <span className="constraint-value">{examTT.metrics?.student_same_day_conflicts || 0}</span>
            </div>
            <div className="exam-constraint-item info">
              <span className="constraint-icon">🎯</span>
              <span className="constraint-label">Fitness Score:</span>
              <span className="constraint-value">{examTT.best_fitness?.toFixed(2) || 'N/A'}</span>
            </div>
          </div>

          {/* AI Explanation for Exam Timetable */}
          {isCoordinator && (
            <div className="ai-explanation-container">
              <button
                className="ai-explanation-toggle"
                onClick={() => setShowExamAIExplanation(!showExamAIExplanation)}
              >
                <span className="ai-icon">🧬</span>
                <span>How was this generated?</span>
                <span className="toggle-arrow">{showExamAIExplanation ? '▲' : '▼'}</span>
              </button>
              {showExamAIExplanation && (
                <div className="ai-explanation-content">
                  <p>
                    <strong>This exam schedule was optimized using a Genetic Algorithm (GA)</strong> that:
                  </p>
                  <ul>
                    <li>🧬 <strong>Evolution:</strong> Simulates natural selection over multiple generations</li>
                    <li>🎯 <strong>Fitness Function:</strong> Minimizes student conflicts and same-day exams</li>
                    <li>🔄 <strong>Crossover:</strong> Combines good schedules to create better ones</li>
                    <li>⚡ <strong>Mutation:</strong> Introduces random changes to explore new solutions</li>
                  </ul>
                  <p><strong>Hard Constraints (Must be 0):</strong></p>
                  <ul>
                    <li>✅ No student has two exams at the same time</li>
                    <li>✅ No room is double-booked</li>
                  </ul>
                  <p><strong>Soft Constraints (Minimized):</strong></p>
                  <ul>
                    <li>⚠️ Reduce same-day exams for students</li>
                    <li>⚠️ Spread exams evenly across time slots</li>
                  </ul>
                  <p className="ai-note">
                    💡 Higher fitness score = better schedule. The GA ran for multiple generations to find this optimal solution.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Exam Filter Bar */}
          {isCoordinator && (
            <div className="filter-bar exam-filter-bar" style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
              <div className="filter-group">
                <label>📅 Date:</label>
                <select value={examFilterDay} onChange={(e) => setExamFilterDay(e.target.value)} className="input" style={{ padding: '4px 8px' }}>
                  <option value="all">All Dates</option>
                  {(() => {
                    const dates = new Set<string>()
                    Object.values(examTT.timeslots || {}).forEach((slot: any) => {
                      const label = slot?.label || ''
                      const date = label.split(' ')[0]
                      if (date && date.match(/^\d{4}-\d{2}-\d{2}$/)) dates.add(date)
                    })
                    return Array.from(dates).sort().map(date => (
                      <option key={date} value={date}>{date}</option>
                    ))
                  })()}
                </select>
              </div>

              <div className="filter-group">
                <label>🕐 Session:</label>
                <select value={examFilterSlot} onChange={(e) => setExamFilterSlot(e.target.value)} className="input" style={{ padding: '4px 8px' }}>
                  <option value="all">All Sessions</option>
                  <option value="Morning">Morning</option>
                  <option value="Evening">Evening</option>
                </select>
              </div>

              {/* NEW: Semester Filter */}
              <div className="filter-group">
                <label>🎓 Semester:</label>
                <select value={examFilterSemester} onChange={(e) => setExamFilterSemester(e.target.value)} className="input" style={{ padding: '4px 8px' }}>
                  <option value="all">All Semesters</option>
                  {(() => {
                    const sems = new Set<string>()
                    Object.keys(examTT.chromosome || {}).forEach((examId) => {
                      // Extract digits (e.g., CSBS03T01 -> 03)
                      const match = examId.match(/(\d{2})/)
                      if (match) sems.add(match[1])
                    })
                    return Array.from(sems).sort().map(s => (
                      <option key={s} value={s}>Sem {parseInt(s)}</option>
                    ))
                  })()}
                </select>
              </div>



              <button
                className="btn-secondary"
                onClick={() => {
                  setExamFilterDay('all'); setExamFilterSlot('all');
                  setExamFilterSemester('all'); setExamFilterSection('all');
                }}
                style={{ marginLeft: 'auto' }}
              >
                Reset
              </button>
            </div>
          )}

          {/* Exam Schedule Table */}
          {examViewMode === 'table' ? (
            <>
              <h4 className="subhead">
                <span className="subhead-icon">📋</span>
                Exam Schedule
                <span className="exam-count-badge">
                  {(() => {
                    const entries = Object.entries(examTT.chromosome || {})
                    const filtered = entries.filter(([examId, slotId]) => {
                      const slotLabel = examTT.timeslots?.[slotId as string]?.label || ''
                      const day = slotLabel.split(' ')[0]
                      const session = slotLabel.includes('Morning') ? 'Morning' : 'Evening'
                      const dept = examId.slice(0, 2)

                      // Filter: Date, Session, Dept
                      if (examFilterDay !== 'all' && day !== examFilterDay) return false
                      if (examFilterDept !== 'all' && dept !== examFilterDept) return false
                      if (examFilterSlot !== 'all' && session !== examFilterSlot) return false

                      // NEW Filter: Semester
                      if (examFilterSemester !== 'all') {
                        const match = examId.match(/(\d{2})/)
                        if (!match || match[1] !== examFilterSemester) return false
                      }

                      // NEW Filter: Section (Look up relevant courses from FullTT)
                      if (examFilterSection !== 'all' && fullTT && fullTT.class_timetable) {
                        // 1. Try to find if this section takes this course
                        // Heuristic: Remove 'EX_' prefix if present to get CourseID
                        const cleanCourseId = examId.replace(/^EX_/, '')

                        // Check if any class entry matches this course AND this section
                        const isTakenBySection = Object.entries(fullTT.class_timetable).some(([key, val]) => {
                          const [cId, sec] = key.split('|')
                          // Check exact ID match or partial inclusion
                          return (cId === cleanCourseId || cId.includes(cleanCourseId)) && sec === examFilterSection
                        })

                        if (!isTakenBySection) return false
                      }

                      return true
                    })
                    return `${filtered.length} exams`
                  })()}
                </span>
              </h4>
              <table className="data-table exam-table">
                <thead>
                  <tr>
                    <th>📝 Exam</th>
                    <th>📅 Date</th>
                    <th>⏰ Time</th>
                    <th>🕐 Session</th>
                    <th>🎓 Semester</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(examTT.chromosome || {})
                    .filter(([examId, slotId]) => {
                      // COPY THE EXACT FILTER LOGIC FROM ABOVE HERE
                      const slotLabel = examTT.timeslots?.[slotId as string]?.label || ''
                      const day = slotLabel.split(' ')[0]
                      const session = slotLabel.includes('Morning') ? 'Morning' : 'Evening'
                      const dept = examId.slice(0, 2)

                      if (examFilterDay !== 'all' && day !== examFilterDay) return false
                      if (examFilterDept !== 'all' && dept !== examFilterDept) return false
                      if (examFilterSlot !== 'all' && session !== examFilterSlot) return false

                      // Semester Check
                      if (examFilterSemester !== 'all') {
                        const match = examId.match(/(\d{2})/)
                        if (!match || match[1] !== examFilterSemester) return false
                      }

                      // Section Check
                      if (examFilterSection !== 'all' && fullTT && fullTT.class_timetable) {
                        const cleanCourseId = examId.replace(/^EX_/, '')
                        const isTakenBySection = Object.entries(fullTT.class_timetable).some(([key]) => {
                          const [cId, sec] = key.split('|')
                          return (cId === cleanCourseId || cId.includes(cleanCourseId)) && sec === examFilterSection
                        })
                        if (!isTakenBySection) return false
                      }

                      return true
                    })
                    .sort(([, a], [, b]) => {
                      const slotA = examTT.timeslots?.[a as string]?.label || ''
                      const slotB = examTT.timeslots?.[b as string]?.label || ''
                      return slotA.localeCompare(slotB)
                    })
                    .map(([examId, slotId]) => {
                      const slotLabel = (examTT.timeslots?.[slotId as string]?.label as string) || ''
                      const [date, session] = slotLabel.split(' ')
                      const dept = examId.slice(0, 2)
                      const semMatch = examId.match(/\d{2}/)
                      const semester = semMatch ? `Sem ${parseInt(semMatch[0])}` : '-'
                      return (
                        <tr key={examId} className={`exam-row exam-${dept.toLowerCase()}`}>
                          <td className="exam-id-cell">
                            <span className="exam-badge">{examId}</span>
                          </td>
                          <td className="exam-date-cell">{date || '-'}</td>
                          <td className="font-mono text-sm">
                            {(() => {
                              const tSlot = examTT.timeslots?.[slotId as string]
                              if (tSlot?.start_time && tSlot?.end_time) {
                                return `${tSlot.start_time} - ${tSlot.end_time}`
                              }
                              // Fallback logic if backend data is stale/missing
                              if (session === 'Morning') return '09:00 - 12:00'
                              if (session === 'Evening') return '14:00 - 17:00'
                              return '-'
                            })()}
                          </td>
                          <td>
                            <span className={`session-badge ${session?.toLowerCase() || ''}`}>
                              {session === 'Morning' ? '🌅 Morning' : '🌆 Evening'}
                            </span>
                          </td>
                          <td>{semester}</td>
                        </tr>
                      )
                    })}
                </tbody>
              </table>
            </>
          ) : (
            /* Calendar View */
            <div className="exam-calendar-view">
              <h4 className="subhead">
                <span className="subhead-icon">📅</span>
                Exam Calendar
              </h4>
              <div className="exam-calendar-grid">
                {(() => {
                  // Group exams by date
                  const examsByDate: Record<string, { morning: string[]; evening: string[] }> = {}
                  Object.entries(examTT.chromosome || {}).forEach(([examId, slotId]) => {
                    const slotLabel = examTT.timeslots?.[slotId as string]?.label || ''
                    const [date, session] = slotLabel.split(' ')
                    const dept = examId.slice(0, 2)
                    if (examFilterDept !== 'all' && dept !== examFilterDept) return
                    if (!date) return
                    if (!examsByDate[date]) examsByDate[date] = { morning: [], evening: [] }
                    if (session === 'Morning') examsByDate[date].morning.push(examId)
                    else examsByDate[date].evening.push(examId)
                  })
                  return Object.entries(examsByDate).sort(([a], [b]) => a.localeCompare(b)).map(([date, exams]) => (
                    <div key={date} className="exam-calendar-day">
                      <div className="calendar-date-header">{date}</div>
                      <div className="calendar-sessions">
                        <div className="calendar-session morning">
                          <div className="session-header">🌅 Morning</div>
                          <div className="session-exams">
                            {exams.morning.map(examId => (
                              <span key={examId} className={`calendar-exam-chip dept-${examId.slice(0, 2).toLowerCase()}`}>
                                {examId}
                              </span>
                            ))}
                            {exams.morning.length === 0 && <span className="no-exams">No exams</span>}
                          </div>
                        </div>
                        <div className="calendar-session evening">
                          <div className="session-header">🌆 Evening</div>
                          <div className="session-exams">
                            {exams.evening.map(examId => (
                              <span key={examId} className={`calendar-exam-chip dept-${examId.slice(0, 2).toLowerCase()}`}>
                                {examId}
                              </span>
                            ))}
                            {exams.evening.length === 0 && <span className="no-exams">No exams</span>}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
                })()}
              </div>
            </div>
          )}

          {isCoordinator && (
            <>
              <button className="btn-link" onClick={() => setShowRawExamTT(!showRawExamTT)} style={{ marginTop: 12 }}>
                {showRawExamTT ? '🔽 Hide' : '▶️ Show'} Raw JSON
              </button>
              {showRawExamTT && (
                <pre className="code-block" style={{ marginTop: 8 }}>
                  {JSON.stringify(examTT, null, 2)}
                </pre>
              )}
            </>
          )}
        </div>
      )}

      {fullTT && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Class & Lab Timetable</h3>
            {isCoordinatorView && (
              <button
                className="btn-secondary"
                onClick={() => downloadText('class_lab_timetable.json', JSON.stringify(fullTT, null, 2))}
              >
                Export JSON
              </button>
            )}
          </div>

          {/* AI Explanation Collapsible */}
          {isCoordinatorView && (
            <div className="ai-explanation-container">
              <button
                className="ai-explanation-toggle"
                onClick={() => setShowAIExplanation(!showAIExplanation)}
              >
                <span className="ai-icon">🤖</span>
                <span>Why this schedule?</span>
                <span className="toggle-arrow">{showAIExplanation ? '▲' : '▼'}</span>
              </button>
              {showAIExplanation && (
                <div className="ai-explanation-content">
                  <p>
                    <strong>This schedule was generated using Constraint Satisfaction Problem (CSP) algorithm</strong> ensuring:
                  </p>
                  <ul>
                    <li>✅ <strong>No room conflicts:</strong> Each room is assigned to only one class/lab per timeslot</li>
                    <li>✅ <strong>No faculty conflicts:</strong> Each teacher teaches only one class at a time</li>
                    <li>✅ <strong>No section conflicts:</strong> Students in the same section don't have overlapping classes</li>
                    <li>✅ <strong>Room capacity:</strong> Room capacity matches or exceeds section size</li>
                    <li>✅ <strong>Teacher availability:</strong> Classes are only scheduled when teachers are available</li>
                    <li>⚡ <strong>Workload balance:</strong> Limited to ~4 classes per teacher per day and ~5 classes per section per day</li>
                  </ul>
                  <p className="ai-note">
                    <em>The algorithm prioritizes spreading classes across weekdays for better student experience.</em>
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Constraint Summary Bar */}
          {isCoordinatorView && constraintMetrics && (
            <>
              <div className="constraint-summary-bar">
                <div className={`constraint-item ${constraintMetrics.roomConflicts === 0 ? 'success' : 'error'}`}>
                  <span className="constraint-icon">{constraintMetrics.roomConflicts === 0 ? '✔' : '✖'}</span>
                  <span className="constraint-label">Room Conflicts:</span>
                  <span className="constraint-value">{constraintMetrics.roomConflicts}</span>
                </div>
                <div className={`constraint-item ${constraintMetrics.facultyConflicts === 0 ? 'success' : 'error'}`}>
                  <span className="constraint-icon">{constraintMetrics.facultyConflicts === 0 ? '✔' : '✖'}</span>
                  <span className="constraint-label">Faculty Conflicts:</span>
                  <span className="constraint-value">{constraintMetrics.facultyConflicts}</span>
                </div>
                <div className={`constraint-item ${constraintMetrics.sectionConflicts === 0 ? 'success' : 'error'}`}>
                  <span className="constraint-icon">{constraintMetrics.sectionConflicts === 0 ? '✔' : '✖'}</span>
                  <span className="constraint-label">Section Conflicts:</span>
                  <span className="constraint-value">{constraintMetrics.sectionConflicts}</span>
                </div>
                <div className={`constraint-item ${constraintMetrics.facultyOverload === 0 ? 'success' : 'warning'}`}>
                  <span className="constraint-icon">{constraintMetrics.facultyOverload === 0 ? '✔' : '⚠'}</span>
                  <span className="constraint-label">Faculty Overload (Soft):</span>
                  <span className="constraint-value">{constraintMetrics.facultyOverload} cases</span>
                </div>
                {(constraintMetrics.roomConflicts > 0 || constraintMetrics.facultyConflicts > 0 ||
                  constraintMetrics.sectionConflicts > 0 || constraintMetrics.facultyOverload > 0) && (
                    <button
                      className="btn-secondary"
                      onClick={() => setShowConflictDetails(!showConflictDetails)}
                      style={{ marginLeft: 'auto' }}
                    >
                      {showConflictDetails ? 'Hide Details' : 'Show Details'}
                    </button>
                  )}
              </div>
              {showConflictDetails && (
                <div className="conflict-details-box">
                  {constraintMetrics.roomConflicts > 0 && (
                    <div className="conflict-section">
                      <h5>🏠 Room Conflicts ({constraintMetrics.roomConflicts}):</h5>
                      <ul>
                        {constraintMetrics.roomConflictDetails?.map((c: string, i: number) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {constraintMetrics.facultyConflicts > 0 && (
                    <div className="conflict-section">
                      <h5>👨‍🏫 Faculty Conflicts ({constraintMetrics.facultyConflicts}):</h5>
                      <ul>
                        {constraintMetrics.facultyConflictDetails?.map((c: string, i: number) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {constraintMetrics.sectionConflicts > 0 && (
                    <div className="conflict-section">
                      <h5>📝 Section Conflicts ({constraintMetrics.sectionConflicts}):</h5>
                      <ul>
                        {constraintMetrics.sectionConflictDetails?.map((c: string, i: number) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {constraintMetrics.facultyOverload > 0 && (
                    <div className="conflict-section">
                      <h5>⚠️ Faculty Overload ({constraintMetrics.facultyOverload}):</h5>
                      <ul>
                        {constraintMetrics.facultyOverloadDetails?.map((c: string, i: number) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* Filter Bar for Coordinator */}
          {isCoordinatorView && (
            <div className="filter-bar">
              <div className="filter-item">
                <label>📅 Day:</label>
                <select value={filterDay} onChange={(e) => setFilterDay(e.target.value)} className="filter-select">
                  <option value="all">All Days</option>
                  {filterOptions.days.map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>
              <div className="filter-item">
                <label>🏛 Dept:</label>
                <select value={filterDept} onChange={(e) => setFilterDept(e.target.value)} className="filter-select">
                  <option value="all">All Depts</option>
                  {filterOptions.departments.map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>
              <div className="filter-item">
                <label>🎓 Semester:</label>
                <select value={filterSemester} onChange={(e) => setFilterSemester(e.target.value)} className="filter-select">
                  <option value="all">All Semesters</option>
                  {filterOptions.semesters.map((s) => (
                    <option key={s} value={s}>Sem {s}</option>
                  ))}
                </select>
              </div>
              <div className="filter-item">
                <label>📝 Section:</label>
                <select value={filterSection} onChange={(e) => setFilterSection(e.target.value)} className="filter-select">
                  <option value="all">All Sections</option>
                  {filterOptions.sections.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div className="filter-item">
                <label>👨‍🏫 Faculty:</label>
                <select value={filterFaculty} onChange={(e) => setFilterFaculty(e.target.value)} className="filter-select">
                  <option value="all">All Faculty</option>
                  {filterOptions.faculties.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>
              <div className="filter-item">
                <label>📚 Type:</label>
                <select value={filterType} onChange={(e) => setFilterType(e.target.value as any)} className="filter-select">
                  <option value="all">All</option>
                  <option value="class">📘 Classes Only</option>
                  <option value="lab">🧪 Labs Only</option>
                </select>
              </div>
              <button
                className="btn-secondary filter-reset"
                onClick={() => {
                  setFilterDay('all')
                  setFilterDept('all')
                  setFilterSection('all')
                  setFilterFaculty('all')
                  setFilterType('all')
                }}
              >
                Reset Filters
              </button>
            </div>
          )}

          {/* Class Schedule */}
          {(filterType === 'all' || filterType === 'class') && (
            <>
              {isCoordinatorView && coordFilteredClassGrid && Object.keys(coordFilteredClassGrid).length > 0 && (
                <>
                  <h4 className="subhead schedule-type-header class-header">
                    <span className="type-icon">📘</span> Class Schedule
                  </h4>
                  {Object.entries(coordFilteredClassGrid).map(([day, slots]) => {
                    const slotKeys = Object.keys(slots).sort()
                    return (
                      <div key={day} style={{ marginBottom: 16 }}>
                        <div className="day-header">{day}</div>
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th style={{ width: '140px' }}>Time</th>
                              <th>Classes</th>
                            </tr>
                          </thead>
                          <tbody>
                            {slotKeys.map((timeKey) => (
                              <tr key={timeKey}>
                                <td>{timeKey}</td>
                                <td>
                                  {slots[timeKey].map((entry, i) => (
                                    <div key={i} className="class-entry class-type-entry">
                                      <span className="entry-icon">📘</span> {entry}
                                    </div>
                                  ))}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )
                  })}
                </>
              )}
              {!isCoordinatorView && filteredClassGrid && (
                <>
                  <h4 className="subhead">Class Schedule (By Day)</h4>
                  {Object.entries(filteredClassGrid).map(([day, slots]) => {
                    const slotKeys = Object.keys(slots).sort()
                    return (
                      <div key={day} style={{ marginBottom: 16 }}>
                        <div className="day-header">{day}</div>
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th style={{ width: '140px' }}>Time</th>
                              <th>Classes</th>
                            </tr>
                          </thead>
                          <tbody>
                            {slotKeys.map((timeKey) => (
                              <tr key={timeKey}>
                                <td>{timeKey}</td>
                                <td>
                                  {slots[timeKey].map((entry, i) => (
                                    <div key={i} className="class-entry">
                                      {entry}
                                    </div>
                                  ))}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )
                  })}
                </>
              )}
              {isStudent && (!filteredClassGrid || Object.keys(filteredClassGrid).length === 0) && (
                <p className="help-text">No classes found for your section. Check the class|section input.</p>
              )}
            </>
          )}

          {/* Lab Schedule */}
          {(filterType === 'all' || filterType === 'lab') && (
            <>
              {isCoordinatorView && coordFilteredLabGrid && Object.keys(coordFilteredLabGrid).length > 0 && (
                <>
                  <h4 className="subhead schedule-type-header lab-header">
                    <span className="type-icon">🧪</span> Lab Schedule
                  </h4>
                  {Object.entries(coordFilteredLabGrid).map(([day, slots]) => {
                    const slotKeys = Object.keys(slots).sort()
                    return (
                      <div key={day} style={{ marginBottom: 16 }}>
                        <div className="day-header lab-day-header">{day}</div>
                        <table className="data-table lab-table">
                          <thead>
                            <tr>
                              <th style={{ width: '140px' }}>Slot</th>
                              <th>Labs</th>
                            </tr>
                          </thead>
                          <tbody>
                            {slotKeys.map((slotKey) => (
                              <tr key={slotKey}>
                                <td>{slotKey}</td>
                                <td>
                                  {slots[slotKey].map((entry, i) => (
                                    <div key={i} className="class-entry lab-type-entry">
                                      <span className="entry-icon">🧪</span> {entry}
                                    </div>
                                  ))}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )
                  })}
                </>
              )}
              {!isCoordinatorView && labGrid && Object.keys(labGrid).length > 0 && (
                <>
                  <h4 className="subhead">Lab Schedule (By Day)</h4>
                  {Object.entries(labGrid).map(([day, slots]) => {
                    const slotKeys = Object.keys(slots).sort()
                    return (
                      <div key={day} style={{ marginBottom: 16 }}>
                        <div className="day-header">{day}</div>
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th style={{ width: '140px' }}>Slot</th>
                              <th>Labs</th>
                            </tr>
                          </thead>
                          <tbody>
                            {slotKeys.map((slotKey) => (
                              <tr key={slotKey}>
                                <td>{slotKey}</td>
                                <td>
                                  {slots[slotKey].map((entry, i) => (
                                    <div key={i} className="class-entry">
                                      {entry}
                                    </div>
                                  ))}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )
                  })}
                </>
              )}
            </>
          )}

          {isCoordinator && (
            <>
              <button className="btn-link" onClick={() => setShowRawFullTT(!showRawFullTT)} style={{ marginTop: 12 }}>
                {showRawFullTT ? 'Hide' : 'Show'} Raw JSON
              </button>
              {showRawFullTT && (
                <pre className="code-block" style={{ marginTop: 8 }}>
                  {JSON.stringify(fullTT, null, 2)}
                </pre>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )

  const renderDataUpload = () => (
    <div>
      <h2 className="section-title">📤 Data Upload</h2>
      {renderLoginBar()}
      {!isCoordinator && <p className="help-text">Only coordinator can upload data.</p>}
      {isCoordinator && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-header">
              <div>
                <h3 className="card-title">🧾 Import University Data</h3>
                <p className="help-text" style={{ margin: 0 }}>
                  Upload CSV/Excel or add rows manually. This updates the dataset used by timetabling and room allocation.
                </p>
              </div>
              <div className="actions">
                <span className="badge" title="Currently selected data type">
                  📦 {String(dataKind).toUpperCase()}
                </span>
              </div>
            </div>
          </div>

          <div className="upload-grid">
            <div className="upload-card">
              <div className="card-header">
                <div>
                  <h3 className="card-title">📎 Upload File</h3>
                  <p className="help-text" style={{ margin: 0 }}>Upload a CSV/Excel file or start from the sample template.</p>
                </div>
              </div>
              <div className="form-row">
                <label>Data type:</label>
                <select value={dataKind} onChange={(e) => setDataKind(e.target.value as any)} className="input">
                  <option value="rooms">Rooms</option>
                  <option value="teachers">Teachers</option>
                  <option value="courses">Courses</option>
                  <option value="students">Students</option>
                  <option value="exams">Exams</option>
                </select>
              </div>

              <div className="dropzone">
                <p className="dropzone-title">🧲 Drag & drop CSV/Excel or click to browse</p>
                <input
                  type="file"
                  accept=".csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
                  onChange={(e) => handleFileSelect(e.target.files?.[0] || null)}
                  className="file-input"
                />
                <div className="file-info">
                  {fileName ? (
                    <span className="badge badge-ok">✅ Selected: {fileName}</span>
                  ) : (
                    <span className="badge badge-warn">⚠️ No file selected</span>
                  )}
                </div>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    setCsvText(sampleTemplates[dataKind])
                    setFileText('')
                    setFileName('')
                  }}
                  style={{ marginTop: 8 }}
                >
                  🧩 Use sample template
                </button>
              </div>
              <button
                onClick={runUpload}
                className="btn-primary"
                disabled={loading || !(csvText.trim() || fileText.trim())}
                style={{ marginTop: 12 }}
              >
                {loading ? 'Uploading...' : '⬆️ Upload & Preview'}
              </button>
              {error && <div className="error-box" style={{ marginTop: 10 }}>{error}</div>}
            </div>

            <div className="upload-card">
              <div className="card-header">
                <div>
                  <h3 className="card-title">✍️ Manual Entry</h3>
                  <p className="help-text" style={{ margin: 0 }}>Fill fields, add rows, then upload & save.</p>
                </div>
                <div className="actions">
                  <span className="badge" title="Rows staged for upload">🧺 Rows: {rows.length}</span>
                </div>
              </div>
              <div className="form-grid">
                {(FIELD_DEFS[dataKind] || []).map((f) => (
                  <div key={f.name} className="form-row">
                    <label>{f.label}{f.required ? ' *' : ''}</label>
                    <input
                      className="input"
                      value={formRow[f.name] || ''}
                      onChange={(e) => setFormRow({ ...formRow, [f.name]: e.target.value })}
                      placeholder={f.label}
                    />
                  </div>
                ))}
              </div>
              <button className="btn-secondary" onClick={addRow} style={{ marginTop: 8 }}>
                ➕ Add row
              </button>

              {rows.length > 0 && (
                <>
                  <h4 className="subhead" style={{ marginTop: 16 }}>👀 Preview</h4>
                  <table className="data-table">
                    <thead>
                      <tr>
                        {(FIELD_DEFS[dataKind] || []).map((f) => <th key={f.name}>{f.label}</th>)}
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r, idx) => (
                        <tr key={idx}>
                          {(FIELD_DEFS[dataKind] || []).map((f) => (
                            <td key={f.name}>{r[f.name]}</td>
                          ))}
                          <td>
                            <button className="btn-link" onClick={() => removeRow(idx)}>Remove</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <button className="btn-primary" onClick={submitRows} style={{ marginTop: 12 }} disabled={loading}>
                    {loading ? 'Uploading...' : '💾 Upload & Save'}
                  </button>
                </>
              )}
            </div>
          </div>

          {uploadResult && (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-header">
                <div>
                  <h3 className="card-title">✅ Upload Result</h3>
                  <p className="help-text" style={{ margin: 0 }}>Parsed rows and a quick preview of the uploaded data.</p>
                </div>
                <div className="actions">
                  <span className="badge">🧮 Rows: {uploadResult.count}</span>
                </div>
              </div>
              <div className="info-row">
                <span className="info-label">Rows parsed:</span>
                <span className="info-value">{uploadResult.count}</span>
              </div>
              <h4 className="subhead">📋 Data Preview</h4>
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      {uploadResult.rows?.[0] &&
                        Object.keys(uploadResult.rows[0]).map((key) => <th key={key}>{key}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {uploadResult.rows?.slice(0, 10).map((row: any, i: number) => (
                      <tr key={i}>
                        {Object.values(row).map((val: any, j: number) => (
                          <td key={j}>{val}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {uploadResult.rows?.length > 10 && (
                <p className="help-text" style={{ marginTop: 8 }}>
                  Showing first 10 rows of {uploadResult.count}
                </p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )

  const mainContent = (
    <div className="app-root">
      <header className="app-header">
        <h1>AI University Scheduler</h1>
        <p>Timetabling, Exams & Room Allocation</p>
      </header>

      <nav className="tab-bar">
        {!isTeacher && (
          <button className={activeTab === 'dashboard' ? 'tab active' : 'tab'} onClick={() => setActiveTab('dashboard')}>
            <TabIcon name="dashboard" />
            <span>Dashboard</span>
          </button>
        )}
        {!isTeacher && !isStudent && (
          <button className={activeTab === 'exam-rooms' ? 'tab active' : 'tab'} onClick={() => setActiveTab('exam-rooms')}>
            <TabIcon name="building" />
            <span>Exam Room Allocation</span>
          </button>
        )}
        <button className={activeTab === 'timetables' ? 'tab active' : 'tab'} onClick={() => setActiveTab('timetables')}>
          <TabIcon name="calendar" />
          <span>Timetables</span>
        </button>
        {!isTeacher && !isStudent && (
          <button className={activeTab === 'data' ? 'tab active' : 'tab'} onClick={() => setActiveTab('data')}>
            <TabIcon name="upload" />
            <span>Data Upload</span>
          </button>
        )}
      </nav>

      <main className="app-main">
        {!isTeacher && activeTab === 'dashboard' && renderDashboard()}
        {!isTeacher && !isStudent && activeTab === 'exam-rooms' && renderExamRooms()}
        {activeTab === 'timetables' && renderTimetables()}
        {!isTeacher && !isStudent && activeTab === 'data' && renderDataUpload()}
      </main>
    </div>
  )

  return (
    <Routes>
      <Route
        path="/login"
        element={
          isLoggedIn ? (
            <Navigate to="/" replace />
          ) : (
            <LoginPage
              email={loginEmail}
              password={loginPassword}
              onEmailChange={setLoginEmail}
              onPasswordChange={setLoginPassword}
              onSubmit={handleLogin}
              authError={authError}
              status={status}
              loading={loading}
            />
          )
        }
      />
      <Route path="/*" element={isLoggedIn ? mainContent : <Navigate to="/login" replace />} />
    </Routes>
  )
}

type LoginPageProps = {
  email: string
  password: string
  onEmailChange: (val: string) => void
  onPasswordChange: (val: string) => void
  onSubmit: () => void
  authError: string | null
  status: any
  loading: boolean
}

function LoginPage({
  email,
  password,
  onEmailChange,
  onPasswordChange,
  onSubmit,
  authError,
  status,
  loading,
}: LoginPageProps) {
  return (
    <div className="auth-page">
      <div className="card auth-card card-glow">
        <div className="auth-header">
          <div>
            <div className="auth-title" style={{ marginBottom: 4 }}>
              AI University Scheduler
            </div>
            <p className="auth-subtitle" style={{ margin: 0 }}>Timetabling, Exams & Room Allocation</p>
          </div>
          <div className="status-chip" style={{ background: status?.status === 'ok' ? '#e8f7f0' : '#fef2f2' }}>
            <span className="status-dot" style={{ background: status?.status === 'ok' ? '#10b981' : '#ef4444' }} />
            <span>{status?.status || 'Checking backend...'}</span>
          </div>
        </div>

        <div className="form-row">
          <label>Email</label>
          <input
            className="input"
            type="email"
            inputMode="email"
            autoComplete="username"
            placeholder="Enter your email"
            spellCheck={false}
            value={email}
            onChange={(e) => onEmailChange(e.target.value)}
          />
        </div>
        <div className="form-row">
          <label>Password</label>
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            placeholder="Enter your password"
            value={password}
            onChange={(e) => onPasswordChange(e.target.value)}
          />
        </div>
        {authError && <div className="error-box" style={{ marginTop: 8 }}>{authError}</div>}
        <button className="btn-primary" onClick={onSubmit} disabled={loading} style={{ width: '100%' }}>
          {loading ? 'Signing in...' : 'Login'}
        </button>
      </div>
    </div>
  )
}

function TabIcon({ name }: { name: 'dashboard' | 'building' | 'calendar' | 'upload' }) {
  const common = {
    className: 'tab-icon',
    width: 16,
    height: 16,
    viewBox: '0 0 24 24',
    fill: 'none',
    xmlns: 'http://www.w3.org/2000/svg',
  } as const

  if (name === 'dashboard') {
    return (
      <svg {...common} aria-hidden="true">
        <path
          d="M3 3h8v10H3V3zm10 0h8v6h-8V3zM3 15h8v6H3v-6zm10-4h8v10h-8V11z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
      </svg>
    )
  }

  if (name === 'building') {
    return (
      <svg {...common} aria-hidden="true">
        <path
          d="M4 21V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v16"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
        <path
          d="M9 21v-6h6v6"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path
          d="M8 7h.01M12 7h.01M16 7h.01M8 10h.01M12 10h.01M16 10h.01"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
      </svg>
    )
  }

  if (name === 'calendar') {
    return (
      <svg {...common} aria-hidden="true">
        <path
          d="M7 3v3M17 3v3"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
        <path
          d="M4 8h16"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
        <path
          d="M6 6h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path
          d="M12 12v4l2 1"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    )
  }

  return (
    <svg {...common} aria-hidden="true">
      <path
        d="M12 3v10"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M8 9l4 4 4-4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  )
}