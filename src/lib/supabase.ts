import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

/** Review row type matching the Supabase schema */
export interface Review {
  id: string;
  platform_name: string;
  author: string | null;
  original_text: string;
  sentiment: "Positive" | "Negative" | "Neutral";
  category: string;
  rating: number | null;
  source_url: string | null;
  subject: string | null;
  is_read: boolean;
  scraped_at: string;
  created_at: string;
}
