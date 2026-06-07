export default function Navbar() {
  return (
    <nav 
    className=" bg-white flex text-2xl items-center gap-4 font-semibold px-6 py-3 shadow-md border border-neutral-300 h-18 rounded-md"
    >
      <div className="h-10 w-10 bg-linear-to-tr from-lime-100  via-lime-500 to-lime-800 rounded-md border border-green-50 shadow-md shadow-green-700/50"></div>
      <div>Satellite View</div>
    </nav>
  )
}