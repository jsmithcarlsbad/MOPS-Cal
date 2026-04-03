// Copyright: Jetty, 2015
// License: Creative Commons:  Attribution, Non-Commercial, Share-alike: CC BY-NC-SA
// https://creativecommons.org/licenses/by-nc-sa/2.0/

// HelmholtzY.scad — Y axis Helmholtz pair. Target: calibrator.ini [coils] resistance_y_ohms = 11.2 Ω (both coils in series).
// AWG 23 enameled copper; coilNumberOfTurns chosen so combined R matches ~11.2 Ω at coilRadius 105 mm.
// X/Z: HelmholtzX.scad, HelmholtzZ.scad

// Helmholtz Coil Design for 3D Printing.  Also this shows statistics about the coil generated, including the
// amount of field generated for a given number of wraps and current.

// Note: The coil diameter  + 2 * flange height must not exceed the width  of the 3D printer bed, and
// 		 The coil radius must not exceed the depth of the 3D printer bed.

// When winding the coils, both coils are wound in the same direction and mounted in the same direction, i.e. the current
// and magentic field in both coils is in the same axis.

// This will also do the calculation to figure out the magentic field strength
// Look in the output of openscad for "Helmholtz Coil Configuration Statistics" 
// Units are predominately nanoTesla (nT), as the earths field is generally measured in nT for magnetometers, if you need Gauss:
// 		1 Guass = 100,000nanoTesla

// Earths field is approximate +/-50,000nT, therefore the coil needs to be capable of at least that if cancelling the earths fields is required
// Kp Index 9 (highest for Aurora) is 500nT difference

// Printing:
//		If the diameter of the coil fits on the printer bed, then print 3 (CompleteCoil), otherwise if the radius of the coil
//		fits on the printed bed, then print 1 and 2 (the coil halves)
//
//		Coil halves - 10% infill, 2 shells and full support (including exterior)
//		Platform - 5% infill, 2 shells
//		Everything else, 10% infill, 2 shells
//
// Assembly:
//		Note the bottom of each coil has a small hole for the wire to go through, when assembling coil halves, make sure you have that
//		hole in each assembled coil.

partnum							= 0;			// 0=All, 1=Coil Half 1, 2=Coil Half 2, 3=CompleteCoil, 4=Coil Retainers, 5=Mounting Block, 6=Platform, 7=Winder hub plate (separate print)


// All the following settings are metric except coilOhmsPerThousandFeet and control the magnetic strength, size of
// the coil and statistics for the coil, they need to be set correctly
coilRadius						= 105;		// Coil Radius in mm's
coilGauge						= 23;		// AWG (reference)
coilNumberOfTurns				= 39;		// Per coil; pair ≈ 11.2 Ω combined @ 20°C copper table
coilWireDiameter					= 0.62;		// Enameled OD (mm) — measure your spool
coilWireFudge					= 0.2;		// Fudge factor in mm's to add to the space for the coil to allow for 3D printer inaccuracy	
coilFormerFlangeHeight			= 2.0;		// The height of the flange, must be at 3X the coilWireDiameter + coilWireFudge to allow for the wire hole
coilFormerFlangeWidth			= 2.0;		// The width of the flange
coilMaxAmps						= 0.5;		// Design max (match Pico / driver limit)
coilOhmsPerThousandFeet			= 66.79;	// AWG 23 copper, Ω per 1000 ft @ ~20°C
coilTargetResistanceIni			= 11.2;		// calibrator.ini [coils] resistance_y_ohms (both coils series)

// These settings effect general coil geometry
coilOuterRingPercentage			= 1 - 0.15;	// The size of the outer ring based on a percentage of the radius
coilInnerRingPercentage			= 0.20;		// The size of the inner ring based on a percentage of the radius

// These settings effect parts of the total object
coilRetainerThickness			= 3;
coilRetainerWidth				= 10;
coilRetainerDepth				= 7;
coilNumRetainers					= 5;			// The number of retainers when partnum=4 (always 2 less than the actual number, as 2 are part of the base
coilMountingBlockThickness		= 7;
coilMountingBlockWidth			= 140;		// It would make sense to make this wide enough to place the mounting posts outside of the coil for
											// magnetic field uniformity reasons
mountingPostBlockHeight			= 25;
mountingPostBlockThickness		= 4;
mountingPostDiameter				= 5.5;
platformHeightAdd				= 10;			// The height of the table can be increased by a positive number here
platformThickness				= 5;
platformPostDiameter				= 10;		// Half of legacy Ø20 — smaller posts + donuts (platform cylinders match)
platformPostReinforcementFudge	= 0.3;			// Post reinforcement diameter fudge factor for fit
// Reinforcement donut: keep ID around post; radial wall = **half** of legacy (+5 mm/side over post Ø) → smaller OD, less X clash with coils.
_platformPostReinforcementInnerR	= platformPostDiameter / 2 + platformPostReinforcementFudge;
_platformPostReinforcementWallLegacy	= (platformPostDiameter / 2 + 5) - _platformPostReinforcementInnerR;
platformPostReinforcementDiameter	= 2 * (_platformPostReinforcementInnerR + _platformPostReinforcementWallLegacy / 2);
platformPostReinforcementHeight	= 10;

// Winder: Helmholtz pair = left + right coil; each coil has insert pockets on BOTH inner-ring faces (mirror); 2× partnum 7 per coil.
// https://www.amazon.com/dp/B0DN6NWQXK
winderCouplingCenterHoleD		= 8.2;
winderHubDiskThickness			= 4;
winderMountScrewD				= 3;
winderMountScrewClearanceD		= 3.4;
winderHeatInsertHoleDiameter	= 4.2;
winderHeatInsertDepth			= 5;
winderMountScrewCount			= 3;
winderHoleAngleOffsetDeg		= 15;
winderMetalFlangeBoltCircleRadius	= 16;
winderMetalFlangeBoltHoleD		= 3.4;
winderMetalFlangeBoltCount		= 4;
winderMetalFlangeAngleOffsetDeg	= 45;
useCoilWinderHub				= true;


// DO NOT CHANGE THESE SETTINGS !
coilFormerWireSpaceThickness		= coilWireDiameter * coilNumberOfTurns + coilWireFudge;	// The space for the wire to fit in on the former
coilOhmsPerMeter					= (coilOhmsPerThousandFeet / 1000.0) / 0.3048;

manifoldCorrection 				= 0.1;


// These are used to figure out the magnetic force for the coil
// Reference: https://en.wikipedia.org/wiki/Helmholtz_coil
// DO NOT CHANGE THESE SETTINGS !
coilStatsUo						= 4 * PI * 1E-7;		// Uo term
coilStatsI						= 1.0;						// Coil current in amps (leave as 1)
coilStatsN						= coilNumberOfTurns;
coilStatsR						= (coilRadius + coilWireDiameter / 2) / 1000;
coilStatsB						= pow( 4/5, 3/2 ) * ((coilStatsUo * coilStatsN * coilStatsI ) / coilStatsR);	// Result is in Teslas	
coilStatsLengthPerCoil			= 2 * PI * coilStatsR * coilStatsN;
coilCombinedResistance			= coilStatsLengthPerCoil * 2 * coilOhmsPerMeter;
coilVoltageRequired				= coilMaxAmps * coilCombinedResistance;
coilMaximumCapacity				= (coilStatsB * 1000000000) * coilMaxAmps;
coilUsableDiameter				= coilRadius * 2/3;
coilUsableLength					= coilRadius; 
innerRingInnerR					= coilUsableDiameter / 2;
innerRingOuterR					= coilUsableDiameter / 2 + coilUsableDiameter * coilInnerRingPercentage;
winderMountBoltCircleRadius		= (innerRingInnerR + innerRingOuterR) / 2;
winderHubDiskRadius				= innerRingOuterR - 0.25;
coilFormerTotalThickness			= coilFormerWireSpaceThickness + coilFormerFlangeWidth * 2;
coilSpokeRotationAngles			= [22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5];
coilSpokeLength					= coilRadius - (coilUsableDiameter / 2) - 2.0;
coilSpokeDimensions				= [0.075 * coilRadius, coilSpokeLength, coilFormerTotalThickness];
coilSpokeOffset					= [0, (coilUsableDiameter + coilSpokeLength) / 2 + 1.0, 0];
coilFormerFlangeOffset			= [0, 0, (coilFormerWireSpaceThickness + coilFormerFlangeWidth) / 2];
coilHalferFlangeDimensions		= [(coilRadius + coilFormerFlangeHeight) * 2,
								   coilRadius + coilFormerFlangeHeight,
								   coilFormerFlangeWidth + manifoldCorrection * 2];
coilHalferWireSpaceDimensions		= [coilRadius * 2, coilRadius, coilFormerWireSpaceThickness + manifoldCorrection * 2];
coilHalferWireSpaceOffset			= [0, coilRadius / 2, 0];
coilHalferFlangeOffset1			= [0, (coilRadius + coilFormerFlangeHeight) / 2 + manifoldCorrection,   coilFormerFlangeOffset[2]];
coilHalferFlangeOffset2			= [coilHalferFlangeOffset1[0], coilHalferFlangeOffset1[1], - coilFormerFlangeOffset[2]];
coilHalferRotataionFlangeAngle	= 7;
coilOffset1						= [0, 			  0,   			   coilRadius / 2];
coilOffset2						= [coilOffset1[0], coilOffset1[1], - coilOffset1[2]];
coilRetainerDimensions			= [coilUsableLength + coilFormerTotalThickness + coilRetainerThickness * 2, coilRetainerWidth, coilRetainerDepth];
coilRetainerBlockDimensions		= [coilRetainerThickness, coilRetainerWidth, coilRetainerThickness];
coilRetainerBlockOffset1			= [(coilFormerTotalThickness + coilRetainerThickness) / 2,
								   0,
								  (coilRetainerDimensions[2] + coilRetainerBlockDimensions[2]) / 2]; 
coilRetainerBlockOffset2			= [- coilRetainerBlockOffset1[0], coilRetainerBlockOffset1[1], coilRetainerBlockOffset1[2]];
coilRetainerLocationAngles		= [-45, 45, 75, 105, 135];
coilRetainerLocationAnglesBlock	= [-15, 15];
coilMountingBlockDimensions		= [coilRetainerDimensions[0], coilMountingBlockWidth, coilMountingBlockThickness];
coilMountingBlockOffset			= [0, 0, - (coilRadius + coilFormerFlangeHeight + coilMountingBlockDimensions[2] / 2) ];
mountingPostBlockWidth			= (coilRadius - (coilFormerWireSpaceThickness + coilFormerFlangeWidth)) - 4;
mountingPostBlockDimensions		= [mountingPostBlockWidth, mountingPostBlockThickness, mountingPostBlockHeight];
mountingPostBlockOffset			= [0, ( coilMountingBlockDimensions[1] - mountingPostBlockDimensions[1] ) / 2,
								   ( mountingPostBlockDimensions[2] + coilMountingBlockDimensions[2] ) / 2];
mountingPostOffset1				= [15, 0, 0]; 
mountingPostOffset2				= [-mountingPostOffset1[0], mountingPostOffset1[1], mountingPostOffset1[2]];
platformDimensions				= [mountingPostBlockWidth, coilUsableDiameter, platformThickness ];
platformOffset					= [0, 0, -(platformThickness / 2 + coilUsableDiameter / 2) + platformHeightAdd];
platformPostSeparationReduceMm	= 5;		// total: posts 5 mm closer (each side −2.5 mm in ±X)
platformPostOffset				= [coilRadius * 0.25 - platformPostSeparationReduceMm / 2, 0, 0];


$fn = 80;


helmholtzStats();



if ( partnum == 0 )
	coilRetainersAll();

if ( partnum == 1 )
	bottomHalfHelmholtzCoil();

if ( partnum == 2 )
	topHalfHelmholtzCoil();

if ( partnum == 3 || partnum == 0 )
	fullHelmholtzCoil();

if ( partnum == 4 )
	coilRetainersAllFlat();

if ( partnum == 5 || partnum == 0 )
	coilMountingBlock();

if ( partnum == 6 || partnum == 0 )
	platform();

if ( partnum == 7 )
	winderHubSeparatePart();

if ( partnum == 0 && useCoilWinderHub )
	translate( [ coilRadius * 2.5, 0, 0 ] )
		winderHubSeparatePart();



module platform()
{
	postHeight				= platformOffset[2] - coilMountingBlockOffset[2] + (coilMountingBlockDimensions[2] + platformThickness) / 2;
	postHeightOffset 		= coilMountingBlockOffset[2] + (postHeight - coilMountingBlockDimensions[2]) / 2;

	translate( platformOffset )
		cube( platformDimensions, center=true );

	translate( platformPostOffset )
		translate( [0, 0, postHeightOffset] )
			cylinder( r=platformPostDiameter / 2, h=postHeight, center=true );

	translate( -platformPostOffset )
		translate( [0, 0, postHeightOffset] )
			cylinder( r=platformPostDiameter / 2, h=postHeight, center=true );
}



module coilMountingBlock()
{
	postReinforcementOffsetZ	= coilMountingBlockOffset[2] + (coilMountingBlockDimensions[2] + platformPostReinforcementHeight) / 2;
	// Slight Z overlap vs mounting cube top avoids coplanar union → CGAL non-manifold warning
	postReinforcementDonutZ	= postReinforcementOffsetZ - manifoldCorrection;

	difference()
	{
		union()
		{
			translate( coilMountingBlockOffset )
			{
				cube( coilMountingBlockDimensions, center=true );

				translate( mountingPostBlockOffset )
					difference()
					{
						cube( mountingPostBlockDimensions, center=true );

						// Mounting post holes
						translate( mountingPostOffset1 )
							rotate( [90, 0, 0] )
								cylinder( r=mountingPostDiameter / 2, h = mountingPostBlockDimensions[1] + manifoldCorrection * 2, center=true );

						translate( mountingPostOffset2 )
							rotate( [90, 0, 0] )
								cylinder( r=mountingPostDiameter / 2, h = mountingPostBlockDimensions[1] + manifoldCorrection * 2, center=true );
					}
			}

			for ( coilRetainerLocationAngle = coilRetainerLocationAnglesBlock )
				rotate( [coilRetainerLocationAngle, 0, 0] )
					translate( [0, 0, -(coilRadius + coilFormerFlangeHeight + coilRetainerDimensions[2] / 2)] )
						coilRetainer();
			// Post reinforcement
			translate( platformPostOffset )
				translate( [0, 0, postReinforcementDonutZ] )
					donut( outerRadius=platformPostReinforcementDiameter / 2,
						   innerRadius = platformPostDiameter / 2 + platformPostReinforcementFudge,
						   height=platformPostReinforcementHeight, center=true );

			translate( -platformPostOffset )
				translate( [0, 0, postReinforcementDonutZ] )
					donut( outerRadius=platformPostReinforcementDiameter / 2,
						   innerRadius = platformPostDiameter / 2 + platformPostReinforcementFudge,
						   height=platformPostReinforcementHeight, center=true );
		}

		// Remove holes in coil mounting block for post reinforcement
		translate( platformPostOffset )
			translate( [0, 0, postReinforcementOffsetZ - coilMountingBlockDimensions[2] / 2] )
				cylinder( r=platformPostDiameter / 2 + platformPostReinforcementFudge,
					  	  h=coilMountingBlockDimensions[2] + platformPostReinforcementHeight + manifoldCorrection * 2,
					  	  center=true ); 

		translate( -platformPostOffset )
			translate( [0, 0, postReinforcementOffsetZ - coilMountingBlockDimensions[2] / 2] )
				cylinder( r=platformPostDiameter / 2 + platformPostReinforcementFudge,
					  	  h=coilMountingBlockDimensions[2] + platformPostReinforcementHeight + manifoldCorrection * 2,
					  	  center=true ); 
	} convexity=10;
}



module coilRetainersAllFlat()

{
	for ( retainerNum = [1:coilNumRetainers] )
			translate( [0, retainerNum * (coilRetainerBlockDimensions[1] + 3), 0] )
				coilRetainer();
}



module coilRetainersAll()

{
	for ( coilRetainerLocationAngle = coilRetainerLocationAngles )
		rotate( [coilRetainerLocationAngle, 0, 0] )
			translate( [0, 0, -(coilRadius + coilFormerFlangeHeight + coilRetainerDimensions[2] / 2)] )
				coilRetainer();
}



module coilRetainer()
{
	cube( coilRetainerDimensions, center=true );
	translate( [coilOffset1[2], 0, 0] )
		coilRetainerBlocks();
	translate( [coilOffset2[2], 0, 0] )
		coilRetainerBlocks();
}



module coilRetainerBlocks()
{
	translate( coilRetainerBlockOffset1 )
		cube( coilRetainerBlockDimensions, center=true );

	translate( coilRetainerBlockOffset2 )
		cube( coilRetainerBlockDimensions, center=true );
}



module fullHelmholtzCoil()
{
	rotate( [0, 90, 0] )
	{
		translate( coilOffset1 )
			helmholtzCoil();
		translate( coilOffset2 )
			helmholtzCoil();

		// Show the usable array grayed out
			// cylinder( r=coilUsableDiameter / 2, h=coilUsableLength, center = true );	
	}
}



module bottomHalfHelmholtzCoil()
{
	difference()
	{
		helmholtzCoil();
		helmholtzCoilHalfer();
	}
}



module topHalfHelmholtzCoil()
{
	difference()
	{
		helmholtzCoil();
			rotate( [0, 0, 180] )
				helmholtzCoilHalfer();
	}
}



module helmholtzCoil()
{
	coilOuterRingThickness = coilOuterRingPercentage * coilRadius;

	difference()
	{
		union()
		{
			// Print the inside outer ring (where the coil gets wrapped around)
			donut( outerRadius=coilRadius, innerRadius = coilOuterRingThickness, height=coilFormerWireSpaceThickness, center=true ); 

			// Print the inside inner ring (where the inside marks the usable volume)
			donut( outerRadius=coilUsableDiameter / 2 + coilUsableDiameter * coilInnerRingPercentage,
				   innerRadius = coilUsableDiameter / 2,
			 	   height=coilFormerTotalThickness, center=true ); 
	
			// Print the coil top outer ring retainer
			color( [1, 0, 0] )
			{
				translate( coilFormerFlangeOffset )
					donut( outerRadius=coilRadius + coilFormerFlangeHeight,
						   innerRadius = coilOuterRingThickness,
						   height=coilFormerFlangeWidth, center=true );

				// Print the coil bottom outer ring retainer
				translate( -coilFormerFlangeOffset )
					donut( outerRadius=coilRadius + coilFormerFlangeHeight,
						   innerRadius = coilOuterRingThickness,
						   height=coilFormerFlangeWidth, center=true ); 
			}

			for ( rotationAngle = coilSpokeRotationAngles )
				rotate( [0, 0, rotationAngle] )
					translate( coilSpokeOffset )
						cube( coilSpokeDimensions, center=true);
		}

		if ( useCoilWinderHub )
			winderInsertHolesInFormer();

		// Hole for wire
		translate( [(coilRadius + coilWireDiameter / 2 + coilWireDiameter + coilWireFudge), 0, 0] )
			cylinder( r=(coilWireDiameter + coilWireFudge) / 2, h = coilFormerTotalThickness + manifoldCorrection * 2, center = true);
	}
}



module winderInsertHolesInFormer()
{
	union()
	{
		for ( i = [ 0 : winderMountScrewCount - 1 ] )
			rotate( [0, 0, winderHoleAngleOffsetDeg + i * (360 / winderMountScrewCount)] )
				translate( [winderMountBoltCircleRadius, 0, coilFormerTotalThickness / 2 - winderHeatInsertDepth] )
					cylinder( h=winderHeatInsertDepth + 0.02, d=winderHeatInsertHoleDiameter, center=false, $fn=32 );
		mirror( [0, 0, 1] )
			for ( i = [ 0 : winderMountScrewCount - 1 ] )
				rotate( [0, 0, winderHoleAngleOffsetDeg + i * (360 / winderMountScrewCount)] )
					translate( [winderMountBoltCircleRadius, 0, coilFormerTotalThickness / 2 - winderHeatInsertDepth] )
						cylinder( h=winderHeatInsertDepth + 0.02, d=winderHeatInsertHoleDiameter, center=false, $fn=32 );
	}
}



module winderHubSeparatePart()
{
	difference()
	{
		cylinder( h=winderHubDiskThickness, r=winderHubDiskRadius, center=true );
		cylinder( h=winderHubDiskThickness + manifoldCorrection * 2, d=winderCouplingCenterHoleD, center=true, $fn=64 );
		for ( i = [ 0 : winderMountScrewCount - 1 ] )
			rotate( [0, 0, winderHoleAngleOffsetDeg + i * (360 / winderMountScrewCount)] )
				translate( [winderMountBoltCircleRadius, 0, 0] )
					cylinder( h=winderHubDiskThickness + manifoldCorrection * 2, d=winderMountScrewClearanceD, center=true, $fn=32 );
		for ( i = [ 0 : winderMetalFlangeBoltCount - 1 ] )
			rotate( [0, 0, winderMetalFlangeAngleOffsetDeg + i * (360 / winderMetalFlangeBoltCount)] )
				translate( [winderMetalFlangeBoltCircleRadius, 0, 0] )
					cylinder( h=winderHubDiskThickness + manifoldCorrection * 2, d=winderMetalFlangeBoltHoleD, center=true, $fn=32 );
	}
}



module helmholtzCoilHalfer()
{
	// Slices a helmholtz coil in half for 3D printing
	rotate( [0, 0, -coilHalferRotataionFlangeAngle / 2] )
		translate( coilHalferWireSpaceOffset )
			cube( coilHalferWireSpaceDimensions, center = true );

	rotate( [0, 0, coilHalferRotataionFlangeAngle / 2] )
		translate( coilHalferFlangeOffset1 )
			cube( coilHalferFlangeDimensions, center = true );

	rotate( [0, 0, coilHalferRotataionFlangeAngle / 2] )
		translate( coilHalferFlangeOffset2 )
			cube( coilHalferFlangeDimensions, center = true );
}



module donut(outerRadius, innerRadius, height)
{
	difference()
	{
		cylinder( r=outerRadius, h = height, center = true);
		cylinder( r=innerRadius, h = height + 20 * manifoldCorrection, center = true);
	}
}


module helmholtzStats()
{
	echo();
	echo("Helmholtz Coil Configuration Statistics:");
	echo( str( "    Axis: Y   Target R (ini): ", coilTargetResistanceIni, " Ohms (pair, series)") );
	echo( str( "    AWG: ", coilGauge) );
	echo( str( "    Coil Diameter: ", (coilRadius / 10) * 2, "cm") );
	echo (str( "    Coil Turns: ", coilNumberOfTurns ) );
	echo( str( "        ", coilStatsB * 1000000000, " nT / ", coilStatsB * 10000, " Gauss per amp") );
	echo( str( "        ", (coilStatsB * 1000000000) / 1000, " nT per mA") );
	echo( str( "        ", "Wire length per coil: ", coilStatsLengthPerCoil, "m" ) );
	echo( str( "        ", "Combined resistance of both coils: ", coilCombinedResistance, "Ohms" ) );
	echo( str( "        ", "Voltage required to drive coil: ", coilVoltageRequired, "Volts @ ", coilMaxAmps, "Amps" ) );
	echo( str( "        ", "Maximum magnetic coil capacity: ", coilMaximumCapacity, "nT for the provded gauge" ) );
	echo( str( "        ", "Usable Volume (Cylinder): ", coilUsableLength, "Length(mm) x ", coilUsableDiameter, "Diameter(mm)" ) );
	if ( useCoilWinderHub )
	{
		echo( "    Winder: 2 coils/axis × 2 plates/coil = 4× partnum 7 per axis pair; each coil L+R sandwich for rigid winding" );
		echo( str( "    Winder: separate hub plate (partnum 7); M", winderMountScrewD, " screws into brass heat-set inserts in former" ) );
		echo( str( "        Insert blind hole: d=", winderHeatInsertHoleDiameter, " mm depth ", winderHeatInsertDepth, " mm (both faces); bolt circle R=", winderMountBoltCircleRadius, " mm" ) );
		echo( str( "        Hub disk r=", winderHubDiskRadius, " mm; center hole d=", winderCouplingCenterHoleD, " mm; metal flange PCD R=", winderMetalFlangeBoltCircleRadius, " mm (", winderMetalFlangeBoltCount, " holes)" ) );
	}

	echo();
}
					

