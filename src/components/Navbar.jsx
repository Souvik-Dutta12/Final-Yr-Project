import { useState, useEffect } from "react"

function Navbar() {
  const [dark, setDark] = useState(false)

  useEffect(() => {
    if (dark) {
      document.body.classList.add("dark-mode")
    } else {
      document.body.classList.remove("dark-mode")
    }
  }, [dark])

  return (
    <div className="navbar bg-gradient-to-r from-green-600 to-emerald-500 text-white px-6 py-4 flex justify-between items-center shadow-lg">
      
      <h1 className="text-xl font-bold">🌱 Krishi Advisor </h1>

      
    </div>
  )
}

export default Navbar

