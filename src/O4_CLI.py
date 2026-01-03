"""CLI interface for Ortho4XP batch tile processing."""

import argparse
import sys
import os
import re
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Tuple, Optional, Dict

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


def parse_hgt_filename(filename: str) -> Optional[Tuple[int, int]]:
    """Parse HGT filename to extract lat/lon coordinates.

    Examples:
        N50E010.hgt -> (50, 10)
        S45W073.hgt -> (-45, -73)

    Returns None if filename doesn't match expected pattern.
    """
    pattern = r'^([NS])(\d{2})([EW])(\d{3})\.hgt$'
    match = re.match(pattern, filename, re.IGNORECASE)
    if not match:
        return None

    ns, lat_str, ew, lon_str = match.groups()
    lat = int(lat_str)
    lon = int(lon_str)

    if ns.upper() == 'S':
        lat = -lat
    if ew.upper() == 'W':
        lon = -lon

    return (lat, lon)


def organize_dem_files(source_dir: str) -> int:
    """Organize DEM .hgt files from a flat directory into Elevation_data structure.

    Copies files from source_dir to Elevation_data/<subfolder>/ where subfolder
    is determined by rounding lat/lon to nearest 10 degrees.

    Returns exit code: 0 on success, 1 on errors.
    """
    import O4_File_Names as FNAMES

    if not os.path.isdir(source_dir):
        print(f"Error: Directory not found: {source_dir}")
        return 1

    elevation_dir = FNAMES.Elevation_dir
    copied = 0
    skipped_invalid = 0
    skipped_exists = 0
    errors = 0

    # Find all .hgt files
    hgt_files = [f for f in os.listdir(source_dir) if f.lower().endswith('.hgt')]

    if not hgt_files:
        print(f"No .hgt files found in {source_dir}")
        return 0

    print(f"Found {len(hgt_files)} .hgt file(s) in {source_dir}")

    for filename in hgt_files:
        coords = parse_hgt_filename(filename)
        if coords is None:
            print(f"  Skipping {filename}: invalid naming pattern")
            skipped_invalid += 1
            continue

        lat, lon = coords
        subfolder = FNAMES.round_latlon(lat, lon)
        dest_dir = os.path.join(elevation_dir, subfolder)
        dest_path = os.path.join(dest_dir, filename)
        source_path = os.path.join(source_dir, filename)

        # Check if destination exists
        if os.path.exists(dest_path):
            print(f"  Skipping {filename}: already exists in {subfolder}/")
            skipped_exists += 1
            continue

        # Create destination directory if needed
        try:
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(source_path, dest_path)
            print(f"  Copied {filename} -> {subfolder}/")
            copied += 1
        except Exception as e:
            print(f"  Error copying {filename}: {e}")
            errors += 1

    # Summary
    print(f"\nSummary:")
    print(f"  Copied: {copied}")
    if skipped_invalid:
        print(f"  Skipped (invalid name): {skipped_invalid}")
    if skipped_exists:
        print(f"  Skipped (already exists): {skipped_exists}")
    if errors:
        print(f"  Errors: {errors}")

    return 1 if errors else 0


def parse_args(args: List[str] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='Ortho4XP',
        description='Generate orthophoto scenery tiles for X-Plane',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build single tile with all steps
  python Ortho4XP.py 47 8

  # Build single tile with specific provider and zoom
  python Ortho4XP.py 47 8 --provider BI --zl 17

  # Build batch from file
  python Ortho4XP.py --batch tiles.txt

  # Build batch with specific steps
  python Ortho4XP.py --batch tiles.txt --steps osm,mesh,dsf

  # Parallel batch processing
  python Ortho4XP.py --batch tiles.txt --workers 4

Tile list file format (one tile per line):
  # Lines starting with # are comments
  47,8
  47,9
  48,8
"""
    )

    # Tile specification
    parser.add_argument('lat', type=int, nargs='?',
                        help='Latitude for single tile')
    parser.add_argument('lon', type=int, nargs='?',
                        help='Longitude for single tile')
    parser.add_argument('--batch', '-b', metavar='FILE',
                        help='File containing tile list (lat,lon per line)')

    # Utility commands
    parser.add_argument('--organize-dem', metavar='DIR',
                        help='Organize DEM .hgt files from DIR into Elevation_data')

    # Step selection
    step_group = parser.add_mutually_exclusive_group()
    step_group.add_argument('--steps', metavar='STEPS',
                            help='Comma-separated steps: osm,mesh,mask,dsf,overlay')
    step_group.add_argument('--osm', action='store_true',
                            help='Run OSM/vector step only')
    step_group.add_argument('--mesh', action='store_true',
                            help='Run mesh step only')
    step_group.add_argument('--mask', action='store_true',
                            help='Run mask step only')
    step_group.add_argument('--dsf', action='store_true',
                            help='Run DSF/imagery step only')
    step_group.add_argument('--overlay', action='store_true',
                            help='Run overlay step only')

    # Provider/ZL override
    parser.add_argument('--provider', '-p', metavar='CODE',
                        help='Override imagery provider code')
    parser.add_argument('--zl', type=int, metavar='INT',
                        help='Override zoom level')

    # Config control
    parser.add_argument('--config', '-c', metavar='FILE',
                        help='Use specific config file')
    parser.add_argument('--global-config', action='store_true',
                        help='Use global config only (ignore tile configs)')

    # Parallelization
    parser.add_argument('--workers', '-w', type=int, default=1,
                        metavar='N', help='Number of parallel tile workers (default: 1)')

    # Output control
    parser.add_argument('--verbose', '-v', action='count', default=1,
                        help='Increase verbosity (can be repeated)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress output except errors')
    parser.add_argument('--no-progress', action='store_true',
                        help='Disable progress bar')

    # Error handling
    parser.add_argument('--fail-fast', action='store_true',
                        help='Stop on first tile error')

    # Build directory
    parser.add_argument('--build-dir', metavar='DIR',
                        help='Custom build directory')

    parsed = parser.parse_args(args)

    # Validation
    organize_dem = getattr(parsed, 'organize_dem', None)

    if organize_dem is None and parsed.batch is None and parsed.lat is None:
        parser.error('Either lat/lon, --batch, or --organize-dem is required')

    if parsed.lat is not None and parsed.lon is None:
        parser.error('lon is required when lat is specified')

    if parsed.batch and parsed.lat is not None:
        parser.error('Cannot use both lat/lon and --batch')

    if organize_dem and (parsed.batch or parsed.lat is not None):
        parser.error('--organize-dem cannot be combined with tile processing')

    return parsed


def parse_tile_list(filepath: str) -> List[Tuple[int, int]]:
    """Parse tile list file.

    Format: lat,lon per line, # for comments, blank lines ignored.
    """
    tiles = []
    with open(filepath, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                parts = line.split(',')
                if len(parts) != 2:
                    raise ValueError("Expected lat,lon format")
                lat = int(parts[0].strip())
                lon = int(parts[1].strip())
                tiles.append((lat, lon))
            except ValueError as e:
                print(f"Warning: Skipping invalid line {line_num}: {line} ({e})")
    return tiles


def get_steps_from_args(args: argparse.Namespace) -> Dict[str, bool]:
    """Determine which steps to run from arguments."""
    if args.steps:
        step_names = [s.strip().lower() for s in args.steps.split(',')]
        return {
            'do_osm': 'osm' in step_names,
            'do_mesh': 'mesh' in step_names,
            'do_mask': 'mask' in step_names,
            'do_dsf': 'dsf' in step_names,
            'do_ovl': 'overlay' in step_names or 'ovl' in step_names,
        }
    elif args.osm:
        return {'do_osm': True, 'do_mesh': False, 'do_mask': False,
                'do_dsf': False, 'do_ovl': False}
    elif args.mesh:
        return {'do_osm': False, 'do_mesh': True, 'do_mask': False,
                'do_dsf': False, 'do_ovl': False}
    elif args.mask:
        return {'do_osm': False, 'do_mesh': False, 'do_mask': True,
                'do_dsf': False, 'do_ovl': False}
    elif args.dsf:
        return {'do_osm': False, 'do_mesh': False, 'do_mask': False,
                'do_dsf': True, 'do_ovl': False}
    elif args.overlay:
        return {'do_osm': False, 'do_mesh': False, 'do_mask': False,
                'do_dsf': False, 'do_ovl': True}
    else:
        # All steps by default (except overlay)
        return {'do_osm': True, 'do_mesh': True, 'do_mask': True,
                'do_dsf': True, 'do_ovl': False}


def build_single_tile(
    lat: int,
    lon: int,
    steps: Dict[str, bool],
    provider: Optional[str],
    zl: Optional[int],
    config_file: Optional[str],
    use_global_config: bool,
    build_dir: Optional[str],
    verbosity: int
) -> Tuple[int, int, bool, str]:
    """Build a single tile (process-safe).

    Imports modules fresh to avoid state sharing between processes.
    """
    # Import modules inside function for process isolation
    import O4_UI_Utils as UI
    import O4_Config_Utils as CFG
    import O4_Vector_Map as VMAP
    import O4_Mesh_Utils as MESH
    import O4_Mask_Utils as MASK
    import O4_Tile_Utils as TILE
    import O4_Overlay_Utils as OVL
    import O4_Imagery_Utils as IMG
    import O4_File_Names as FNAMES

    UI.verbosity = verbosity
    UI.gui = None
    UI.is_working = False  # Must be False - build functions check this to prevent re-entry
    UI.red_flag = False

    # Initialize imagery providers (required for fresh imports)
    IMG.initialize_extents_dict()
    IMG.initialize_color_filters_dict()
    IMG.initialize_providers_dict()
    IMG.initialize_combined_providers_dict()

    try:
        tile = CFG.Tile(lat, lon, build_dir or '')

        if config_file:
            tile.read_from_config(config_file=config_file)
        else:
            tile.read_from_config(use_global=use_global_config)

        if provider:
            tile.default_website = provider
        if zl:
            tile.default_zl = zl

        if steps['do_osm'] or steps['do_mesh'] or steps['do_dsf']:
            tile.make_dirs()

        if steps['do_osm']:
            VMAP.build_poly_file(tile)
            if UI.red_flag:
                return (lat, lon, False, "OSM step failed")

        if steps['do_mesh']:
            MESH.build_mesh(tile)
            if UI.red_flag:
                return (lat, lon, False, "Mesh step failed")

        if steps['do_mask']:
            MASK.build_masks(tile)
            if UI.red_flag:
                return (lat, lon, False, "Mask step failed")

        if steps['do_dsf']:
            TILE.build_tile(tile)
            # Retry incomplete images
            tile_coords = FNAMES.short_latlon(lat, lon)
            if tile_coords in IMG.incomplete_imgs:
                TILE.delete_incomplete_imgs(tile)
                TILE.build_tile(tile)
            if UI.red_flag:
                return (lat, lon, False, "DSF step failed")

        if steps['do_ovl']:
            OVL.build_overlay(lat, lon)
            if UI.red_flag:
                return (lat, lon, False, "Overlay step failed")

        return (lat, lon, True, "Success")

    except Exception as e:
        import traceback
        return (lat, lon, False, f"{e}\n{traceback.format_exc()}")


def run_batch(
    tiles: List[Tuple[int, int]],
    steps: Dict[str, bool],
    provider: Optional[str],
    zl: Optional[int],
    config_file: Optional[str],
    use_global_config: bool,
    build_dir: Optional[str],
    workers: int,
    verbosity: int,
    fail_fast: bool,
    show_progress: bool
) -> int:
    """Run batch tile processing.

    Returns exit code: 0 if all succeeded, 1 if any failed.
    """
    if not tiles:
        print("No tiles to process")
        return 0

    results = []
    failed = []

    # Progress bar setup
    pbar = None
    if show_progress and HAS_TQDM:
        pbar = tqdm(total=len(tiles), desc="Tiles", unit="tile")
    elif show_progress:
        print(f"Processing {len(tiles)} tile(s)...")

    start_time = time.time()

    if workers == 1:
        # Sequential processing
        for i, (lat, lon) in enumerate(tiles):
            if not show_progress or not HAS_TQDM:
                print(f"[{i+1}/{len(tiles)}] Processing tile {lat:+d},{lon:+d}...")

            result = build_single_tile(
                lat, lon, steps, provider, zl,
                config_file, use_global_config, build_dir, verbosity
            )
            results.append(result)

            if pbar:
                pbar.update(1)
                status = "OK" if result[2] else "FAIL"
                pbar.set_postfix_str(f"{result[0]:+d},{result[1]:+d} [{status}]")

            if not result[2]:
                failed.append(result)
                if fail_fast:
                    break
    else:
        # Parallel processing
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    build_single_tile,
                    lat, lon, steps, provider, zl,
                    config_file, use_global_config, build_dir, verbosity
                ): (lat, lon)
                for lat, lon in tiles
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

                if pbar:
                    pbar.update(1)
                    status = "OK" if result[2] else "FAIL"
                    pbar.set_postfix_str(f"{result[0]:+d},{result[1]:+d} [{status}]")

                if not result[2]:
                    failed.append(result)
                    if fail_fast:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

    if pbar:
        pbar.close()

    elapsed = time.time() - start_time

    # Summary
    print(f"\n{'='*60}")
    print(f"Batch complete: {len(results) - len(failed)}/{len(tiles)} tiles succeeded")
    print(f"Total time: {elapsed:.1f}s")

    if failed:
        print(f"\nFailed tiles:")
        for lat, lon, _, msg in failed:
            # Only show first line of error message
            short_msg = msg.split('\n')[0][:60]
            print(f"  {lat:+d},{lon:+d}: {short_msg}")
        return 1

    return 0


def main(args: List[str] = None) -> int:
    """Main CLI entry point."""
    parsed = parse_args(args)

    # Handle utility commands
    if parsed.organize_dem:
        return organize_dem_files(parsed.organize_dem)

    # Set verbosity
    verbosity = 0 if parsed.quiet else parsed.verbose
    show_progress = not parsed.no_progress and not parsed.quiet

    # Get tiles to process
    if parsed.batch:
        if not os.path.exists(parsed.batch):
            print(f"Error: Batch file not found: {parsed.batch}")
            return 1
        tiles = parse_tile_list(parsed.batch)
        if not tiles:
            print(f"Error: No valid tiles found in {parsed.batch}")
            return 1
        print(f"Loaded {len(tiles)} tile(s) from {parsed.batch}")
    else:
        tiles = [(parsed.lat, parsed.lon)]

    # Get steps
    steps = get_steps_from_args(parsed)

    step_names = [k.replace('do_', '') for k, v in steps.items() if v]
    print(f"Steps: {', '.join(step_names)}")

    if parsed.workers > 1:
        print(f"Workers: {parsed.workers}")

    # Run batch
    return run_batch(
        tiles=tiles,
        steps=steps,
        provider=parsed.provider,
        zl=parsed.zl,
        config_file=parsed.config,
        use_global_config=parsed.global_config,
        build_dir=parsed.build_dir,
        workers=parsed.workers,
        verbosity=verbosity,
        fail_fast=parsed.fail_fast,
        show_progress=show_progress
    )
