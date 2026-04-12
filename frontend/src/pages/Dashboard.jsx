import { useState } from "react"
import Navbar from "../components/Navbar"
import MapSection from "../components/MapSection"
import ResultPanel from "../components/ResultPanel"
import InfoCards from "../components/InfoCards"
import Loader from "../components/Loader"

function Dashboard() {
  const [location, setLocation] = useState(null)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)

  const handleAnalyze = () => {
    if (!location) return alert("Select a location")

    setLoading(true)

    setTimeout(() => {
      setData({
        soil: "Alluvial",
        crop: "Rice, Wheat",
        water: "Moderate",
        quality: "Good",
      })
      setLoading(false)
    }, 2000)
  }

  return (
    <div className="bg-mist-900 min-h-screen">
      <Navbar />

      <div className="max-w-5xl mx-auto p-6">
        <h1 className="text-3xl text-green-400 font-bold mb-2">
          Smart Soil & Crop Prediction System
        </h1>
        <p className="text-gray-400 mb-4">
          AI-powered satellite analysis for better farming decisions
        </p>

        <MapSection setLocation={setLocation} />

        <button
          onClick={handleAnalyze}
          className="mt-4 bg-green-600 outline-none hover:bg-green-700 text-white font-semibold px-6 py-2 rounded-full shadow-md"
        >
          Analyze Soil
        </button>

        {loading && <Loader />}
        <ResultPanel data={data} />
        <InfoCards />
      </div>
    </div>
  )
}

export default Dashboard