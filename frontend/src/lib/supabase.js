import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL  = import.meta.env.VITE_SUPABASE_URL  || ''
const SUPABASE_ANON = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

// Guard: createClient throws if URL is empty (env vars not configured yet)
export const supabase = SUPABASE_URL ? createClient(SUPABASE_URL, SUPABASE_ANON) : null
