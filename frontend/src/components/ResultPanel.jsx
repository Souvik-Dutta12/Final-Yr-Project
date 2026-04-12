function ResultPanel({ data }) {
  if (!data) return null

  return (
    <div className="bg-[#1c1c1c] mt-6 p-6 rounded-xl shadow-xl grid place-items-center grid-cols-2 gap-4">
      <div className="bg-gray-900 w-2/5 rounded-2xl border-2 border-amber-50 p-3">
        <p className="text-gray-500">🌱 Soil Type</p>
        <h2 className="text-xl text-green-700 font-bold">{data.soil}</h2>
      </div>

      <div className="bg-gray-900 w-2/5 rounded-2xl border-2 border-amber-50 p-3">
        <p className="text-gray-500">🌾 Crop</p>
        <h2 className="text-xl  text-green-700 font-bold">{data.crop}</h2>
      </div>

      <div className="bg-gray-900 w-2/5 rounded-2xl border-2 border-amber-50 p-3">
        <p className="text-gray-500">💧 Water Need</p>
        <h2 className="text-xl  text-green-700 font-bold">{data.water}</h2>
      </div>

      <div className="bg-gray-900 w-2/5 rounded-2xl border-2 border-amber-50 p-3">
        <p className="text-gray-500">🧪 Soil Quality</p>
        <h2 className="text-xl  text-green-700 font-bold">{data.quality}</h2>
      </div>
    </div>
  )
}

export default ResultPanel
