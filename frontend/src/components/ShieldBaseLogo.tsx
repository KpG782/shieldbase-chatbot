interface ShieldBaseLogoProps {
  className?: string;
}

export function ShieldBaseLogo({ className = "h-9 w-9" }: ShieldBaseLogoProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      viewBox="0 0 240 240"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M120 20L40 55V115C40 167.8 74.2 217.2 120 230C165.8 217.2 200 167.8 200 115V55L120 20Z"
        fill="url(#shieldbase_grad)"
      />
      <path
        d="M120 45L65 70V115C65 151.2 88.5 185.1 120 196.3V45Z"
        fill="white"
        fillOpacity="0.15"
      />
      <rect fill="white" height="70" rx="4" width="30" x="105" y="85" />
      <rect fill="white" height="30" rx="4" width="70" x="85" y="105" />
      <defs>
        <linearGradient
          gradientUnits="userSpaceOnUse"
          id="shieldbase_grad"
          x1="40"
          x2="200"
          y1="20"
          y2="230"
        >
          <stop stopColor="#0051D5" />
          <stop offset="1" stopColor="#131B2E" />
        </linearGradient>
      </defs>
    </svg>
  );
}
