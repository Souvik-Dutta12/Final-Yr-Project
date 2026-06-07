export function Tooltip({ content, position = "top", variant = "default", children }) {
    const variants = {
      default: "bg-neutral-900",
      info:    "bg-blue-700",
      success: "bg-green-700",
      warning: "bg-amber-700",
      danger:  "bg-red-700",
    };
  
    const arrowBase = "absolute w-0 h-0 border-[5px] border-transparent left-1/2 -translate-x-1/2";
    const arrowColor = {
      default: "border-t-neutral-900",
      info:    "border-t-blue-700",
      success: "border-t-green-700",
      warning: "border-t-amber-700",
      danger:  "border-t-red-700",
    };
  
    const positions = {
      top:    "bottom-[calc(100%+8px)] left-1/2 -translate-x-1/2 origin-bottom ",
      bottom: "top-[calc(100%+8px)]  left-1/2 -translate-x-1/2 origin-top",
      left:   "right-[calc(100%+8px)] top-1/2 -translate-y-1/2 origin-right",
      right:  "left-[calc(100%+8px)]  top-1/2 -translate-y-1/2 origin-left",
    };
  
    return (
      <span className="relative inline-flex group">
        {children}
        <span
          role="tooltip"
          className={`
            pointer-events-none absolute z-50 whitespace-nowrap
            opacity-0 scale-95 translate-y-1
            group-hover:opacity-100 group-hover:scale-100 group-hover:translate-y-0
            transition-all duration-150 ease-out
            ${positions[position]}
          `}
        >
          <span className={`block text-white text-xs px-2.5 py-1.5 rounded-lg ${variants[variant]}`}>
            {content}
          </span>
          {/* Arrow — only for top/bottom for now */}
          {position === "top" && (
            <span className={`${arrowBase} top-full ${arrowColor[variant]} border-b-0`} />
          )}
          {position === "bottom" && (
            <span className={`${arrowBase} bottom-full border-t-0 ${arrowColor[variant].replace("border-t", "border-b")}`} />
          )}
        </span>
      </span>
    );
  }