import * as React from "react";
import { cn } from "@/lib/utils";

export interface VitalIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

/**
 * Blood Pressure Icon (Droplet)
 */
export const BloodPressureIcon: React.FC<VitalIconProps> = ({
  className,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={cn("h-6 w-6", className)}
    {...props}
  >
    <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
  </svg>
);

/**
 * Heart Rate Icon
 */
export const HeartRateIcon: React.FC<VitalIconProps> = ({
  className,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={cn("h-6 w-6", className)}
    {...props}
  >
    <path d="M20.42 4.58a5.4 5.4 0 0 0-7.65 0l-.77.78-.77-.78a5.4 5.4 0 0 0-7.65 0C1.46 6.7 1.33 10.28 4 13l8 8 8-8c2.67-2.72 2.54-6.3.42-8.42z" />
    <path d="M3.5 12h6l2-4 2 8 2-4h6" />
  </svg>
);

/**
 * SPO2 / Oxygen Icon (Lungs)
 */
export const SPO2Icon: React.FC<VitalIconProps> = ({ className, ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={cn("h-6 w-6", className)}
    {...props}
  >
    <path d="M9 11a3 3 0 1 0 6 0" />
    <path d="M12 2v8" />
    <path d="M12 14v8" />
    <path d="M9.5 8.5 7 6" />
    <path d="M14.5 8.5 17 6" />
    <path d="M9.5 15.5 7 18" />
    <path d="M14.5 15.5 17 18" />
  </svg>
);

/**
 * Temperature Icon (Thermometer)
 */
export const TemperatureIcon: React.FC<VitalIconProps> = ({
  className,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={cn("h-6 w-6", className)}
    {...props}
  >
    <path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z" />
  </svg>
);

/**
 * Respiratory Rate Icon (Wind/Breath)
 */
export const RespiratoryRateIcon: React.FC<VitalIconProps> = ({
  className,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={cn("h-6 w-6", className)}
    {...props}
  >
    <path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2" />
  </svg>
);

/**
 * Weight Icon (Scale)
 */
export const WeightIcon: React.FC<VitalIconProps> = ({
  className,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={cn("h-6 w-6", className)}
    {...props}
  >
    <path d="M3 3v18h18" />
    <path d="M7 16V9" />
    <path d="M12 16V6" />
    <path d="M17 16v-4" />
  </svg>
);

/**
 * Height Icon (Ruler)
 */
export const HeightIcon: React.FC<VitalIconProps> = ({
  className,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={cn("h-6 w-6", className)}
    {...props}
  >
    <path d="M3 3v18h18" />
    <path d="M7 3v18" />
    <path d="M12 3v18" />
    <path d="M17 3v18" />
  </svg>
);

/**
 * BMI Icon
 */
export const BMIIcon: React.FC<VitalIconProps> = ({ className, ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={cn("h-6 w-6", className)}
    {...props}
  >
    <circle cx="12" cy="8" r="5" />
    <path d="M20 21a8 8 0 1 0-16 0" />
  </svg>
);

/**
 * Glucose Icon (Drop with Plus)
 */
export const GlucoseIcon: React.FC<VitalIconProps> = ({
  className,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={cn("h-6 w-6", className)}
    {...props}
  >
    <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
    <line x1="12" y1="10" x2="12" y2="16" />
    <line x1="9" y1="13" x2="15" y2="13" />
  </svg>
);
