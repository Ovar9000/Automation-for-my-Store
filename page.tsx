import { createClient } from '@/utils/supabase/server'
import { cookies } from 'next/headers'

export default async function Page() {
  const cookieStore = await cookies()
  const supabase = createClient(cookieStore)

  const { data: todos } = await supabase.from('todos').select()

  return (
    <div className="p-8 font-sans max-w-xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Sari-Sari Store Cloud Portal</h1>
      <ul className="divide-y divide-gray-200">
        {todos?.map((todo: any) => (
          <li key={todo.id} className="py-2">{todo.name}</li>
        ))}
      </ul>
    </div>
  )
}
